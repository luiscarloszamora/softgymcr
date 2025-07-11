from app import app, db, Usuario, Gimnasio
from werkzeug.security import generate_password_hash
import sys

def listar_usuarios():
    usuarios = Usuario.query.all()
    print("\n📋 Usuarios registrados:")
    for u in usuarios:
        print(f"🧑 Usuario: {u.username} | Gimnasio ID: {u.gimnasio_id}")
    print()

def cambiar_contrasena():
    username = input("🔐 Usuario a modificar: ").strip()
    usuario = Usuario.query.filter_by(username=username).first()
    if usuario:
        nueva = input("🆕 Nueva contraseña: ").strip()
        usuario.contrasena_hash = generate_password_hash(nueva)
        db.session.commit()
        print("✅ Contraseña actualizada.")
    else:
        print("❌ Usuario no encontrado.")

def eliminar_usuario():
    username = input("🗑️ Usuario a eliminar: ").strip()
    usuario = Usuario.query.filter_by(username=username).first()
    if usuario:
        confirmar = input(f"⚠️ ¿Estás seguro de eliminar a '{username}'? (s/n): ").lower()
        if confirmar == "s":
            db.session.delete(usuario)
            db.session.commit()
            print("✅ Usuario eliminado.")
        else:
            print("❎ Cancelado.")
    else:
        print("❌ Usuario no encontrado.")

def crear_usuario():
    nombre_gym = input("🏋️ Nombre del gimnasio: ").strip()
    ubicacion = input("📍 Ubicación del gimnasio: ").strip()
    username = input("🧑 Nombre de usuario: ").strip()
    contrasena = input("🔐 Contraseña: ").strip()

    if Usuario.query.filter_by(username=username).first():
        print("⚠️ Ese usuario ya existe.")
        return

    gimnasio = Gimnasio(nombre=nombre_gym, ubicacion=ubicacion)
    db.session.add(gimnasio)
    db.session.commit()

    usuario = Usuario(
        username=username,
        contrasena_hash=generate_password_hash(contrasena),
        gimnasio_id=gimnasio.id
    )
    db.session.add(usuario)
    db.session.commit()

    print("✅ Usuario y gimnasio creados.")

def menu():
    while True:
        print("\n🛠️ Herramienta de administración de usuarios")
        print("1. Listar usuarios")
        print("2. Cambiar contraseña")
        print("3. Eliminar usuario")
        print("4. Crear nuevo usuario")
        print("5. Salir")

        opcion = input("📥 Elegí una opción: ")

        if opcion == "1":
            listar_usuarios()
        elif opcion == "2":
            cambiar_contrasena()
        elif opcion == "3":
            eliminar_usuario()
        elif opcion == "4":
            crear_usuario()
        elif opcion == "5":
            print("👋 ¡Listo! Saliendo...")
            break
        else:
            print("❌ Opción inválida.")

if __name__ == "__main__":
    with app.app_context():
        menu()
