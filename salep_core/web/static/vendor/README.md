# web/static/vendor — Three.js yerel kopyası (BOŞ, internet yok)

Bu dizine şunlar konacak (bir kez internet olan yerde):

- `three.module.js` (Three.js ~700 KB)
- `OrbitControls.js`

Kaynak: three.js resmi sürümü (r160+; `examples/jsm/controls/OrbitControls.js`
`three` importunu `./three.module.js` göreli yoluna çevirir — dosya
`vendor/three/` altında yan yana durur).

CDN YASAK (§9.21 G19): 3D sekmesi (`js/world3d.js`) yalnız bu dizinden
tembel yüklenir; dizin boşken 3D sekmesi not düşer, 2D sekme tam çalışır.
