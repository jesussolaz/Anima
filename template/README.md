# Plantilla ARPG — gameplay NATIVO C++

El gameplay (PlayerController, ThirdPersonCamera, EnemyAI) ya **no es Python**.
Son componentes C++ nativos del motor (doctrina C++):
`source/gameengine/Flipendo/FL_ArpgComponents.cpp` + `FL_ArpgCore.hpp`.

Se atan a un objeto poniéndole una propiedad de juego **`fl_component`**
(string) con valor `"PlayerController"`, `"ThirdPersonCamera"` o `"EnemyAI"`.
El motor los instancia y tickea solo (FL_ComponentManager).
