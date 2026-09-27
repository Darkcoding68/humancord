from flask import Flask, render_template, request, redirect, session
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config["SECRET_KEY"] = "anonim-chat-secret-key"

socketio = SocketIO(
    app,
    cors_allowed_origins="*"
)

connected_users = {}
active_calls = {}


@app.route("/")
def login():
    if "username" in session:
        return redirect("/chat")

    return render_template("login.html")


@app.route("/login", methods=["POST"])
def do_login():
    username = request.form.get("username", "").strip()

    if not username:
        return redirect("/")

    session["username"] = username[:20]

    return redirect("/chat")


@app.route("/chat")
def chat():
    if "username" not in session:
        return redirect("/")

    return render_template(
        "index.html",
        username=session["username"]
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


def get_users():
    users = []

    for sid, data in connected_users.items():
        users.append({
            "sid": sid,
            "username": data["username"]
        })

    return users


def clear_call(sid):
    other = active_calls.pop(sid, None)

    if other:
        active_calls.pop(other, None)

    return other


@socketio.on("connect")
def handle_connect():
    username = session.get("username")

    if not username:
        return False

    connected_users[request.sid] = {
        "username": username[:20]
    }

    emit(
        "user_list",
        get_users(),
        broadcast=True
    )


@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid

    other = clear_call(sid)

    connected_users.pop(sid, None)

    if other and other in connected_users:
        emit(
            "call_ended",
            {"from": sid},
            to=other
        )

    emit(
        "user_list",
        get_users(),
        broadcast=True
    )


@socketio.on("message")
def handle_message(data):
    username = session.get("username", "Anonim")

    message = str(
        data.get("message", "")
    ).strip()

    if not message:
        return

    message = message[:500]

    emit(
        "message",
        {
            "username": username[:20],
            "message": message
        },
        broadcast=True
    )


@socketio.on("call_user")
def call_user(data):
    target = data.get("target")
    offer = data.get("offer")
    call_type = data.get("type", "voice")

    if not target or not offer:
        return

    if target not in connected_users:
        return

    if request.sid in active_calls:
        emit(
            "call_busy",
            {"message": "Zaten bir aramadasın."},
            to=request.sid
        )
        return

    if target in active_calls:
        emit(
            "call_busy",
            {"message": "Bu kullanıcı şu anda başka bir aramada."},
            to=request.sid
        )
        return

    active_calls[request.sid] = target
    active_calls[target] = request.sid

    username = session.get(
        "username",
        "Anonim"
    )

    emit(
        "incoming_call",
        {
            "from": request.sid,
            "username": username[:20],
            "offer": offer,
            "type": call_type
        },
        to=target
    )


@socketio.on("answer_call")
def answer_call(data):
    target = data.get("target")
    answer = data.get("answer")

    if not target or not answer:
        return

    if target not in connected_users:
        return

    emit(
        "call_answered",
        {
            "from": request.sid,
            "answer": answer
        },
        to=target
    )


@socketio.on("ice_candidate")
def ice_candidate(data):
    target = data.get("target")
    candidate = data.get("candidate")

    if not target or not candidate:
        return

    if target not in connected_users:
        return

    emit(
        "ice_candidate",
        {
            "from": request.sid,
            "candidate": candidate
        },
        to=target
    )


@socketio.on("reject_call")
def reject_call(data):
    target = data.get("target")

    if not target:
        return

    if target not in connected_users:
        return

    clear_call(request.sid)

    emit(
        "call_rejected",
        {
            "from": request.sid
        },
        to=target
    )


@socketio.on("end_call")
def end_call(data):
    target = data.get("target")

    if not target:
        return

    if target not in connected_users:
        clear_call(request.sid)
        return

    clear_call(request.sid)

    emit(
        "call_ended",
        {
            "from": request.sid
        },
        to=target
    )


if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=True
    )