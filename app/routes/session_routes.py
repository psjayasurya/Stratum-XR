from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import List, Dict
import uuid
from datetime import datetime
from app.services.websocket_manager import manager
from app.services.mom_service import mom_service

router = APIRouter()

# In-memory storage for session data (Replace with DB in production)
# {
#   "session_id": {
#       "participants": ["email1", "email2"],
#       "annotations": [
#           {"id": "1", "type": "point", "text": "Rebar here", "timestamp": "..."}
#       ]
#   }
# }
session_store: Dict[str, dict] = {}


def _find_socket_by_id(session_id: str, socket_id: str):
    for sock in manager.active_connections.get(session_id, []):
        if str(id(sock)) == socket_id:
            return sock
    return None

def _init_session_state(session_id: str):
    if session_id not in session_store:
        session_store[session_id] = {
            "participants": [],
            "annotations": [],
            "transcripts": [],
            "ruler": {
                "tab": "line",
                "points": [],
                "units": {},
                "updated_at": None
            },
            "survey": {
                "points": [],
                "is_drawing": False,
                "spacing": 1.0,
                "rotation": 0.0,
                "generated": False,
                "updated_at": None
            },
            "depth": {
                "slice_active": False,
                "slice2d_active": False,
                "depth_value": None,
                "updated_at": None
            },
            "draw": {
                "ops": [],
                "updated_at": None
            },
            "camera": {
                "position": None,
                "target": None,
                "updated_at": None
            },
            "model": {
                "link_all": False,
                "main": {"pos": None, "scale": None, "rot_deg": None},
                "grids": {"pos": None, "scale": None, "rot_deg": None},
                "updated_at": None
            },
            "locks": {},
            "socket_users": {}
        }

def _get_session_state(session_id: str) -> dict:
    _init_session_state(session_id)
    return session_store[session_id]

class SessionManager:
    @staticmethod
    def create_session():
        session_id = str(uuid.uuid4())[:8]
        _init_session_state(session_id)
        return session_id

    @staticmethod
    def add_participant(session_id: str, email: str):
        state = _get_session_state(session_id)
        if email not in state["participants"]:
            state["participants"].append(email)
        return True

    @staticmethod
    def add_annotation(session_id: str, annotation: dict):
        if session_id in session_store:
            annotation['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            session_store[session_id]["annotations"].append(annotation)
            return True
        return False

        return False

    @staticmethod
    def add_transcript(session_id: str, transcript: dict):
        if session_id in session_store:
            transcript['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            session_store[session_id]["transcripts"].append(transcript)
            return True
        return False

    @staticmethod
    def get_session(session_id: str):
        return session_store.get(session_id)

@router.post("/create")
async def create_session():
    session_id = SessionManager.create_session()
    return {"session_id": session_id}

@router.post("/{session_id}/finalize")
async def finalize_session(session_id: str):
    session = SessionManager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    participants = session["participants"]
    annotations = session["annotations"]
    transcripts = session.get("transcripts", [])
    
    if not participants:
       return {"message": "No participants to send email to.", "success": False}

    try:
        # Generate PDF
        print(f"Generating MoM PDF for session {session_id}")
        print(f"Participants: {participants}")
        print(f"Annotations count: {len(annotations)}")
        print(f"Transcripts count: {len(transcripts)}")
        
        pdf_buffer = mom_service.generate_pdf(session_id, annotations, participants, transcripts)
        print(f"PDF generated successfully, size: {pdf_buffer.tell()} bytes")
        
        # Send Email
        print(f"Attempting to send email to {len(participants)} participants...")
        mom_service.send_email(participants, pdf_buffer, session_id)
        
        return {
            "message": f"MoM sent successfully to {len(participants)} participant(s)", 
            "success": True,
            "recipients": participants
        }
    except ValueError as e:
        print(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error finalizing session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send MoM: {str(e)}")


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)
    state = _get_session_state(session_id)
    try:
        while True:
            data = await websocket.receive_json()
            # Handle different message types
            msg_type = data.get("type")
            
            if msg_type == "join":
                email = data.get("email")
                SessionManager.add_participant(session_id, email)
                socket_id = str(id(websocket))
                state["socket_users"][socket_id] = email

                # Tell the newly joined client its peer id for targeted WebRTC signaling.
                await websocket.send_json({
                    "type": "join_ack",
                    "peer_id": socket_id,
                    "session_id": session_id
                })

                # Broadcast participant update
                await manager.broadcast(session_id, {
                    "type": "participant_update",
                    "count": len(state["socket_users"]),
                    "participants": state["participants"],
                    "peer_ids": list(state["socket_users"].keys())
                })
                
            elif msg_type == "annotation_add":
                annotation = data.get("data")
                SessionManager.add_annotation(session_id, annotation)
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "annotation_delete":
                ann_id = data.get("id")
                if ann_id:
                    state["annotations"] = [a for a in state["annotations"] if a.get("id") != ann_id]
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "annotation_clear":
                state["annotations"] = []
                await manager.broadcast(session_id, data, exclude_socket=websocket)
                
            elif msg_type == "camera_sync":
                # Store and forward camera transform to others
                state["camera"] = {
                    "position": data.get("position"),
                    "target": data.get("target"),
                    "rig_position": data.get("rig_position"),
                    "is_vr": bool(data.get("is_vr", False)),
                    "updated_at": datetime.now().isoformat()
                }
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "ruler_tab":
                state["ruler"]["tab"] = data.get("tab", state["ruler"]["tab"])
                state["ruler"]["updated_at"] = datetime.now().isoformat()
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "ruler_point":
                point = data.get("point")
                point_geo = data.get("point_geo")
                if point:
                    state["ruler"]["points"].append({
                        "point": point,
                        "point_geo": point_geo
                    })
                    state["ruler"]["updated_at"] = datetime.now().isoformat()
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "ruler_clear":
                state["ruler"]["points"] = []
                state["ruler"]["updated_at"] = datetime.now().isoformat()
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "survey_point":
                point = data.get("point")
                if point:
                    state["survey"]["points"].append(point)
                    state["survey"]["updated_at"] = datetime.now().isoformat()
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "survey_state":
                state["survey"]["is_drawing"] = bool(data.get("is_drawing"))
                if "spacing" in data:
                    state["survey"]["spacing"] = float(data.get("spacing") or 0)
                if "rotation" in data:
                    state["survey"]["rotation"] = float(data.get("rotation") or 0)
                state["survey"]["updated_at"] = datetime.now().isoformat()
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "survey_clear":
                state["survey"]["points"] = []
                state["survey"]["generated"] = False
                state["survey"]["updated_at"] = datetime.now().isoformat()
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "survey_generate":
                points = data.get("points") or []
                state["survey"]["points"] = points
                state["survey"]["spacing"] = float(data.get("spacing") or 0)
                state["survey"]["rotation"] = float(data.get("rotation") or 0)
                state["survey"]["generated"] = True
                state["survey"]["updated_at"] = datetime.now().isoformat()
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "depth_state":
                state["depth"] = {
                    "slice_active": bool(data.get("slice_active")),
                    "slice2d_active": bool(data.get("slice2d_active")),
                    "depth_value": data.get("depth_value"),
                    "updated_at": datetime.now().isoformat()
                }
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "draw_stroke":
                stroke = data.get("data")
                if stroke:
                    state["draw"]["ops"].append(stroke)
                    # Keep bounded history to avoid unbounded memory growth.
                    if len(state["draw"]["ops"]) > 5000:
                        state["draw"]["ops"] = state["draw"]["ops"][-5000:]
                    state["draw"]["updated_at"] = datetime.now().isoformat()
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "draw_clear":
                state["draw"]["ops"] = []
                state["draw"]["updated_at"] = datetime.now().isoformat()
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "model_transform":
                state["model"] = {
                    "link_all": bool(data.get("link_all")),
                    "active_grid_index": data.get("active_grid_index"),
                    "main": data.get("main") or {},
                    "grids": data.get("grids") or {},
                    "updated_at": datetime.now().isoformat()
                }
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "transcript":
                transcript = data.get("data")
                SessionManager.add_transcript(session_id, transcript)
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "signal":
                sender_id = str(id(websocket))
                target_peer_id = data.get("target_peer_id")

                if target_peer_id:
                    target_socket = _find_socket_by_id(session_id, target_peer_id)
                    if target_socket:
                        await target_socket.send_json({
                            "type": "signal",
                            "from_peer_id": sender_id,
                            "target_peer_id": target_peer_id,
                            "data": data.get("data")
                        })
                else:
                    # Backward-compatible fallback: fan out when target is missing.
                    payload = {
                        "type": "signal",
                        "from_peer_id": sender_id,
                        "data": data.get("data")
                    }
                    await manager.broadcast(session_id, payload, exclude_socket=websocket)

            elif msg_type == "call_start":
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "call_end":
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "audio_data":
                # Broadcast audio frames over WebSocket (fallback when TURN fails)
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "lock_acquire":
                resource_id = data.get("resource_id")
                owner = data.get("owner")
                request_id = data.get("request_id")
                if resource_id and owner:
                    existing = state["locks"].get(resource_id)
                    if not existing or existing.get("owner") == owner:
                        state["locks"][resource_id] = {
                            "owner": owner,
                            "updated_at": datetime.now().isoformat()
                        }
                        await websocket.send_json({
                            "type": "lock_granted",
                            "resource_id": resource_id,
                            "owner": owner,
                            "request_id": request_id
                        })
                    else:
                        await websocket.send_json({
                            "type": "lock_denied",
                            "resource_id": resource_id,
                            "owner": existing.get("owner"),
                            "request_id": request_id
                        })

            elif msg_type == "lock_release":
                resource_id = data.get("resource_id")
                owner = data.get("owner")
                if resource_id and owner:
                    existing = state["locks"].get(resource_id)
                    if existing and existing.get("owner") == owner:
                        state["locks"].pop(resource_id, None)
                        await manager.broadcast(session_id, {
                            "type": "lock_released",
                            "resource_id": resource_id,
                            "owner": owner
                        })

            elif msg_type == "sync_request":
                 # Send current state to requester (for late joiners)
                 await websocket.send_json({
                     "type": "sync_state",
                     "state": {
                         "annotations": state.get("annotations", []),
                         "ruler": state.get("ruler", {}),
                         "survey": state.get("survey", {}),
                         "depth": state.get("depth", {}),
                         "draw": state.get("draw", {}),
                         "camera": state.get("camera", {}),
                         "model": state.get("model", {}),
                         "participants": state.get("participants", [])
                     }
                 })

    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)
        # Release locks owned by this user
        owner = state.get("socket_users", {}).pop(str(id(websocket)), None)
        if owner:
            to_release = [k for k, v in state.get("locks", {}).items() if v.get("owner") == owner]
            for key in to_release:
                state["locks"].pop(key, None)
            if to_release:
                await manager.broadcast(session_id, {
                    "type": "locks_released",
                    "owner": owner,
                    "resources": to_release
                })
        # Remove participant and notify
        if owner and owner in state.get("participants", []):
            state["participants"] = [p for p in state["participants"] if p != owner]
            await manager.broadcast(session_id, {
                "type": "participant_update",
                "count": len(state["socket_users"]),
                "participants": state["participants"],
                "peer_ids": list(state["socket_users"].keys())
            })
