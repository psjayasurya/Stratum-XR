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

class SessionManager:
    @staticmethod
    def create_session():
        session_id = str(uuid.uuid4())[:8]
        session_store[session_id] = {
            "participants": [],
            "annotations": [],
            "transcripts": []
        }
        return session_id

    @staticmethod
    def add_participant(session_id: str, email: str):
        if session_id not in session_store:
            return False
        if email not in session_store[session_id]["participants"]:
            session_store[session_id]["participants"].append(email)
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
    try:
        while True:
            data = await websocket.receive_json()
            # Handle different message types
            msg_type = data.get("type")
            
            if msg_type == "join":
                email = data.get("email")
                SessionManager.add_participant(session_id, email)
                # Broadcast participant update
                await manager.broadcast(session_id, {
                    "type": "participant_update",
                    "count": len(session_store[session_id]["participants"]),
                    "participants": session_store[session_id]["participants"]
                })
                
            elif msg_type == "annotation_add":
                annotation = data.get("data")
                SessionManager.add_annotation(session_id, annotation)
                await manager.broadcast(session_id, data, exclude_socket=websocket)
                
            elif msg_type == "camera_sync":
                # Forward camera transform to others
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "transcript":
                transcript = data.get("data")
                SessionManager.add_transcript(session_id, transcript)
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "signal":
                await manager.broadcast(session_id, data, exclude_socket=websocket)

            elif msg_type == "sync_request":
                 # Send current state to requester (optional, for late joiners)
                 pass

    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)
        # Handle cleanup or notify others if necessary
