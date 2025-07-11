# ✨==================== IMPORTACIONES ====================
import os
from datetime import datetime, timedelta
from functools import wraps

# Flask: framework principal para la app web
from flask import Flask, request, render_template, redirect, url_for, flash, session

# SQLAlchemy: ORM para manejar la base de datos
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate  # Para migraciones de base de datos

# Werkzeug: para encriptar y verificar contraseñas
from werkzeug.security import generate_password_hash, check_password_hash

# Date: tipo de dato específico para fechas en SQLAlchemy
from sqlalchemy import Date
#Filtra el resumen de accesos diarios de clientes por id_gimnasio en especifico
from sqlalchemy import or_

# ⚙️==================== CONFIGURACIÓN ====================
app = Flask(__name__)
app.secret_key = "superclave123"  # Clave secreta para sesiones y seguridad

# Configuración de la base de datos SQLite
basedir = os.path.abspath(os.path.dirname(__file__))  # Ruta absoluta del directorio actual
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'clientes.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Desactiva notificaciones innecesarias

# Inicialización de la base de datos y migraciones
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# 🧱==================== MODELOS ====================
# Representan las tablas de la base de datos

class Gimnasio(db.Model):
    """Tabla que representa un gimnasio"""
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    ubicacion = db.Column(db.String(100))

class Usuario(db.Model):
    """Usuarios que pueden iniciar sesión y están asociados a un gimnasio"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    contrasena_hash = db.Column(db.String(200), nullable=False)
    gimnasio_id = db.Column(db.Integer, db.ForeignKey('gimnasio.id'), nullable=False)
    gimnasio = db.relationship('Gimnasio', backref='usuarios')

class Cliente(db.Model):
    """Clientes registrados en un gimnasio con membresía y vencimiento"""
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    membresia = db.Column(db.String(50), nullable=False)
    vencimiento = db.Column(Date, nullable=False)
    gimnasio_id = db.Column(db.Integer, db.ForeignKey('gimnasio.id'), nullable=False)
    gimnasio = db.relationship('Gimnasio', backref='clientes')

class Pago(db.Model):
    """Registro de pagos realizados por los clientes"""
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    tipo_membresia = db.Column(db.String(20), nullable=False)  # Día, Semanal, etc.
    monto = db.Column(db.Float, nullable=False)
    fecha_pago = db.Column(db.Date, default=datetime.utcnow)
    fecha_vencimiento = db.Column(db.Date, nullable=False)

    cliente = db.relationship('Cliente', backref='pagos')

class AccesoLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=True)
    gimnasio_id = db.Column(db.Integer, nullable=False)  # ← Nuevo campo obligatorio
    nombre_cliente = db.Column(db.String(100))
    estado = db.Column(db.String(20))  # 'ACEPTADO', 'RECHAZADO', 'NO_VALIDO'
    motivo = db.Column(db.String(100))
    fecha = db.Column(db.Date, default=datetime.now().date)
    hora = db.Column(db.Time, default=datetime.now().time)

    cliente = db.relationship('Cliente', backref='accesos')



# 🔒==================== AUTENTICACIÓN ====================
def login_requerido(f):
    """
    Decorador que protege rutas: redirige al login si el usuario no ha iniciado sesión.
    """
    @wraps(f)
    def decorador(*args, **kwargs):
        if 'usuario_id' not in session:
            flash("⚠️ Inicia sesión primero", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorador

# 🧭==================== RUTAS ====================

@app.route("/")
def inicio():
    """Página de inicio simple"""
    return render_template("inicio.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Permite a los usuarios iniciar sesión.
    Verifica credenciales y guarda el ID del usuario y gimnasio en la sesión.
    """
    if request.method == "POST":
        username = request.form["username"]
        contrasena = request.form["contrasena"]
        usuario = Usuario.query.filter_by(username=username).first()

        if usuario and check_password_hash(usuario.contrasena_hash, contrasena):
            session["usuario_id"] = usuario.id
            session["gimnasio_id"] = usuario.gimnasio_id
            flash("🔓 Acceso concedido", "success")
            return redirect(url_for("lista_clientes"))
        else:
            flash("❌ Usuario o contraseña inválidos", "danger")

    return render_template("login.html")

@app.route("/clientes")
@login_requerido
def lista_clientes():
    """
    Muestra la lista de clientes del gimnasio del usuario logueado.
    También calcula el estado de la membresía (ACTIVA o VENCIDA).
    """
    gimnasio_id = session.get("gimnasio_id")
    clientes = Cliente.query.filter_by(gimnasio_id=gimnasio_id).all()

    for cliente in clientes:
        if cliente.vencimiento:
            cliente.estado = "VENCIDA" if cliente.vencimiento < datetime.now().date() else "ACTIVA"
        else:
            cliente.estado = "DESCONOCIDO"

    return render_template("clientes.html", clientes=clientes)

@app.route("/registro", methods=["GET", "POST"])
@login_requerido
def registro():
    """
    Permite registrar un nuevo cliente y su primer pago.
    Calcula automáticamente la fecha de vencimiento según el tipo de membresía.
    """
    if request.method == "POST":
        nombre = request.form["nombre"].strip()
        membresia = request.form["membresia"].strip()
        monto = request.form["monto"].strip()
        gimnasio_id = session.get("gimnasio_id")

        if not nombre or not membresia or not monto:
            flash("⚠️ Todos los campos son obligatorios.", "danger")
        else:
            hoy = datetime.today().date()
            duraciones = {
                'Mensual': 30,
                'Quincenal': 15,
                'Semanal': 7,
                'Día': 1
            }
            dias = duraciones.get(membresia, 0)
            vencimiento = hoy + timedelta(days=dias)

            # Crear cliente
            nuevo_cliente = Cliente(
                nombre=nombre,
                membresia=membresia,
                vencimiento=vencimiento,
                gimnasio_id=gimnasio_id
            )
            db.session.add(nuevo_cliente)
            db.session.commit()

            # Crear pago asociado
            nuevo_pago = Pago(
                cliente_id=nuevo_cliente.id,
                tipo_membresia=membresia,
                monto=float(monto),
                fecha_pago=hoy,
                fecha_vencimiento=vencimiento
            )
            db.session.add(nuevo_pago)
            db.session.commit()

            flash("✅ Cliente y pago registrados con éxito.", "success")
            return redirect(url_for("lista_clientes"))

    return render_template("registro.html")


@app.route("/editar/<int:id>", methods=["GET", "POST"])
@login_requerido
def editar_cliente(id):
    """
    Permite editar los datos de un cliente.
    Recalcula la fecha de vencimiento según la nueva membresía.
    """
    cliente = Cliente.query.get_or_404(id)

    if cliente.gimnasio_id != session.get("gimnasio_id"):
        flash("❌ Acceso denegado", "danger")
        return redirect(url_for("lista_clientes"))

    if request.method == "POST":
        cliente.nombre = request.form["nombre"]
        cliente.membresia = request.form["membresia"]

        hoy = datetime.today().date()
        duraciones = {
            'Mensual': 30,
            'Quincenal': 15,
            'Semanal': 7,
            'Día': 1
        }
        cliente.vencimiento = hoy + timedelta(days=duraciones.get(cliente.membresia, 0))
        db.session.commit()
        flash("✅ Cliente actualizado con éxito.", "success")
        return redirect(url_for("lista_clientes"))

    return render_template("editar.html", cliente=cliente)

@app.route("/eliminar/<int:id>")
@login_requerido
def eliminar_cliente(id):
    """
    Elimina un cliente si pertenece al gimnasio del usuario actual.
    """
    cliente = Cliente.query.get_or_404(id)

    if cliente.gimnasio_id != session.get("gimnasio_id"):
        flash("❌ No puedes eliminar clientes de otro gimnasio.", "danger")
        return redirect(url_for("lista_clientes"))

    db.session.delete(cliente)
    db.session.commit()
    return redirect(url_for("lista_clientes"))

@app.route("/panel_acceso", methods=["GET", "POST"])
@login_requerido
def panel_acceso():
    """
    Muestra un panel con teclado numérico para ingresar el ID del cliente.
    Redirige a la verificación de acceso.
    """
    if request.method == "POST":
        id = request.form.get("cliente_id")
        return redirect(url_for("verificar_acceso_por_id", id=id))
    return render_template("panel_acceso.html")

@app.route("/acceso_id/<int:id>")
@login_requerido
def verificar_acceso_por_id(id):
    gimnasio_id = session.get("gimnasio_id")
    hoy = datetime.now().date()
    ahora = datetime.now().time()
    cliente = Cliente.query.get(id)
    estado = ""
    motivo = ""

    if id <= 0 or len(str(id)) > 6:
        estado = "NO_VALIDO"
        motivo = "ID inválido o manipulado"
        nombre = f"ID {id}"
        cliente = None
        acceso_permitido = False
    elif not cliente or cliente.gimnasio_id != gimnasio_id:
        estado = "RECHAZADO"
        motivo = "Cliente no registrado o fuera del gimnasio"
        nombre = f"ID {id}"  # ← no usamos nombre de cliente si no pertenece
        cliente = None
        acceso_permitido = False

    else:
        acceso_permitido = cliente.vencimiento >= hoy
        nombre = cliente.nombre
        estado = "ACEPTADO" if acceso_permitido else "RECHAZADO"
        motivo = "" if acceso_permitido else "Membresía vencida"

    # Registrar intento
    log = AccesoLog(
        cliente_id=cliente.id if cliente else None,
        gimnasio_id=gimnasio_id,
        nombre_cliente=nombre,
        estado=estado,
        motivo=motivo,
        fecha=hoy,
        hora=ahora
    )
    db.session.add(log)
    db.session.commit()

    return render_template("verificar_acceso.html", cliente=cliente, acceso_permitido=acceso_permitido)


@app.route("/estado_acceso_diario")
@login_requerido
def estado_acceso_diario():
    hoy = datetime.now().date()
    gimnasio_id = session.get("gimnasio_id")

    accesos = AccesoLog.query.filter(
        AccesoLog.fecha == hoy,
        AccesoLog.gimnasio_id == gimnasio_id  # ← filtra por gimnasio
    ).order_by(AccesoLog.hora.desc()).all()

    return render_template("estado_acceso_diario.html", accesos=accesos, hoy=hoy)




@app.route("/registrar_pago/<int:cliente_id>", methods=["GET", "POST"])
@login_requerido
def registrar_pago(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    if request.method == "POST":
        tipo = request.form["tipo_membresia"]
        monto = float(request.form["monto"])

        dias = {"Día": 1, "Semanal": 7, "Quincenal": 15, "Mensual": 30}
        hoy = datetime.now().date()
        base = cliente.vencimiento if cliente.vencimiento and cliente.vencimiento >= hoy else hoy
        fecha_vencimiento = base + timedelta(days=dias[tipo])


        nuevo_pago = Pago(
            cliente_id=cliente.id,
            tipo_membresia=tipo,
            monto=monto,
            fecha_pago=hoy,
            fecha_vencimiento=fecha_vencimiento
        )
        db.session.add(nuevo_pago)

        # Actualiza vencimiento del cliente
        cliente.vencimiento = fecha_vencimiento
        cliente.membresia = tipo
        db.session.commit()

        flash("✅ Pago registrado y vencimiento actualizado.", "success")
        return redirect(url_for("lista_clientes"))

    return render_template("registrar_pago.html", cliente=cliente)

@app.route("/historial_pagos/<int:cliente_id>")
@login_requerido
def historial_pagos(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    pagos = Pago.query.filter_by(cliente_id=cliente_id).order_by(Pago.fecha_pago.desc()).all()
    return render_template("historial_pagos.html", cliente=cliente, pagos=pagos)

@app.route("/cierres", methods=["GET", "POST"])
@login_requerido
def cierre_contable():
    gimnasio_id = session.get("gimnasio_id")
    pagos = []
    total = 0
    fecha_inicio = fecha_fin = None

    if request.method == "POST":
        fecha_inicio = datetime.strptime(request.form["fecha_inicio"], "%Y-%m-%d").date()
        fecha_fin = datetime.strptime(request.form["fecha_fin"], "%Y-%m-%d").date()

        pagos = Pago.query.join(Cliente).filter(
            Cliente.gimnasio_id == gimnasio_id,
            Pago.fecha_pago.between(fecha_inicio, fecha_fin)
        ).order_by(Pago.fecha_pago.desc()).all()

        total = sum(p.monto for p in pagos)

    # Resumen diario solo del gimnasio actual
    hoy = datetime.now().date()
    pagos_hoy = Pago.query.join(Cliente).filter(
        Cliente.gimnasio_id == gimnasio_id,
        Pago.fecha_pago == hoy
    ).all()

    ingresos_hoy = sum(p.monto for p in pagos_hoy)
    clientes_hoy = len(set(p.cliente_id for p in pagos_hoy))
    promedio_hoy = ingresos_hoy / len(pagos_hoy) if pagos_hoy else 0

    tipos = {}
    for p in pagos_hoy:
        tipos[p.tipo_membresia] = tipos.get(p.tipo_membresia, 0) + 1

    return render_template(
        "cierre_contable.html",
        pagos=pagos,
        total=total,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        ingresos_hoy=ingresos_hoy,
        clientes_hoy=clientes_hoy,
        promedio_hoy=promedio_hoy,
        tipos=tipos,
        hoy=hoy
    )



@app.route("/logout")
def logout():
    """
    Cierra la sesión del usuario actual.
    """
    session.clear()
    flash("🔒 Sesión cerrada correctamente", "info")
    return redirect(url_for("login"))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

# 🚀================