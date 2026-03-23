
(function () {
    function initEarth() {
        const container = document.getElementById('earth-container');
        if (!container) return;

        // Ensure Three.js is loaded
        if (typeof THREE === 'undefined') {
            const script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';
            script.onload = () => {
                runRealEarth(container);
            };
            document.head.appendChild(script);
        } else {
            runRealEarth(container);
        }
    }

    function runRealEarth(container) {
        // Scene setup
        const scene = new THREE.Scene();

        let width = container.clientWidth;
        let height = container.clientHeight;

        const camera = new THREE.PerspectiveCamera(45, width / height, 0.01, 1000);
        camera.position.z = 1.6;

        const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
        renderer.setSize(width, height);
        renderer.setPixelRatio(window.devicePixelRatio);

        container.innerHTML = '';
        container.appendChild(renderer.domElement);

        // --- Lighting ---
        scene.add(new THREE.AmbientLight(0x444444));

        const sunLight = new THREE.DirectionalLight(0xffffff, 1.2);
        sunLight.position.set(5, 3, 5);
        scene.add(sunLight);

        // --- Earth Mesh ---
        const radius = 0.6;
        const segments = 64;
        const geometry = new THREE.SphereGeometry(radius, segments, segments);

        const textureLoader = new THREE.TextureLoader();

        const earthMap = textureLoader.load('https://raw.githubusercontent.com/mrdoob/three.js/master/examples/textures/planets/earth_atmos_2048.jpg');
        const earthSpecular = textureLoader.load('https://raw.githubusercontent.com/mrdoob/three.js/master/examples/textures/planets/earth_specular_2048.jpg');
        const earthNormal = textureLoader.load('https://raw.githubusercontent.com/mrdoob/three.js/master/examples/textures/planets/earth_normal_2048.jpg');

        const material = new THREE.MeshPhongMaterial({
            map: earthMap,
            specularMap: earthSpecular,
            normalMap: earthNormal,
            specular: new THREE.Color(0x333333),
            shininess: 15
        });

        const earthGroup = new THREE.Group();
        const earth = new THREE.Mesh(geometry, material);
        earthGroup.add(earth);
        scene.add(earthGroup);

        // --- Clouds ---
        const cloudGeo = new THREE.SphereGeometry(radius + 0.01, segments, segments);
        const cloudTex = textureLoader.load('https://raw.githubusercontent.com/mrdoob/three.js/master/examples/textures/planets/earth_clouds_2048.png');

        const cloudMat = new THREE.MeshPhongMaterial({
            map: cloudTex,
            transparent: true,
            opacity: 0.8,
            blending: THREE.AdditiveBlending,
            side: THREE.DoubleSide
        });

        const clouds = new THREE.Mesh(cloudGeo, cloudMat);
        earthGroup.add(clouds);

        // --- GPR SCANNING EFFECTS ---

        // 1. Horizontal Scanning Ring (Scanning Depth)
        const ringGeo = new THREE.TorusGeometry(radius + 0.02, 0.003, 16, 100);
        const ringMat = new THREE.MeshBasicMaterial({
            color: 0x81c995, // Match site primary
            transparent: true,
            opacity: 0.6
        });
        const scanRing = new THREE.Mesh(ringGeo, ringMat);
        scanRing.rotation.x = Math.PI / 2;
        scene.add(scanRing);

        // 2. Vertical Scanning Beam (GPR Antenna Line)
        const beamGeo = new THREE.PlaneGeometry(0.01, radius * 2.1);
        const beamMat = new THREE.MeshBasicMaterial({
            color: 0x81c995,
            transparent: true,
            opacity: 0.4,
            side: THREE.DoubleSide
        });
        const scanBeam = new THREE.Mesh(beamGeo, beamMat);

        // Pivot group for rotation around the globe
        const beamPivot = new THREE.Group();
        scene.add(beamPivot);

        // Position beam slightly outside the globe surface
        scanBeam.position.z = radius + 0.02;
        beamPivot.add(scanBeam);

        // 3. Scanning Glow / Pulsing Light
        const scanPoint = new THREE.PointLight(0x81c995, 2, 0.5);
        scanPoint.position.set(0, 0, radius + 0.1);
        beamPivot.add(scanPoint);

        // Small cube representing the "GPR Device"
        const deviceGeo = new THREE.BoxGeometry(0.04, 0.02, 0.04);
        const deviceMat = new THREE.MeshPhongMaterial({ color: 0x5f6368 });
        const device = new THREE.Mesh(deviceGeo, deviceMat);
        device.position.set(0, 0, radius + 0.04);
        beamPivot.add(device);

        // --- Animation Loop ---
        let time = 0;
        const animate = () => {
            requestAnimationFrame(animate);
            time += 0.01;

            // Globe Rotation
            earth.rotation.y += 0.002;
            clouds.rotation.y += 0.0023;
            clouds.rotation.x += 0.0003;

            // Scanning Ring Animation (Moves up and down)
            scanRing.position.y = Math.sin(time * 0.5) * (radius - 0.1);
            scanRing.scale.setScalar(1 + Math.abs(Math.cos(time * 0.5)) * 0.1); // Slight pulse
            scanRing.material.opacity = 0.3 + Math.abs(Math.sin(time)) * 0.4;

            // GPR Device & Vertical Beam Animation (Rotates around the globe)
            beamPivot.rotation.y += 0.005;
            beamPivot.rotation.x = Math.sin(time * 0.3) * 0.2; // Slight wobble for "scanning" feel

            // Device "scanning" jitter
            device.position.y = Math.sin(time * 10) * 0.01;
            scanBeam.material.opacity = 0.2 + Math.random() * 0.2; // Flicker effect

            renderer.render(scene, camera);
        };

        animate();

        // Handle Resize
        const onResize = () => {
            if (!container) return;
            width = container.clientWidth;
            height = container.clientHeight;
            renderer.setSize(width, height);
            camera.aspect = width / height;
            camera.updateProjectionMatrix();
        };

        window.addEventListener('resize', onResize);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initEarth);
    } else {
        initEarth();
    }
})();
