// The parts of three.js the 3D models use (static/models3d.js) — bundled by scripts/build_three.sh into
// static/vendor/three-m3d.min.js. A class models3d.js starts using goes here, then the bundle is built again.
export { WebGLRenderer, Scene, OrthographicCamera, Group, Mesh, MeshStandardMaterial, MeshBasicMaterial, HemisphereLight, DirectionalLight,
  LatheGeometry, ExtrudeGeometry, CylinderGeometry, ConeGeometry, SphereGeometry, BoxGeometry, CircleGeometry, Shape, Vector2, Color,
  DoubleSide, SRGBColorSpace } from 'three';
