"""
Socket.IO Events for Real-Time Live Streaming
- WebRTC Signaling (offer/answer/ICE candidates)
- Live Chat
- Viewer Count Tracking
"""
from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from datetime import datetime

# Track active viewers per stream
stream_viewers = {}  # {stream_id: set(user_ids/session_ids)}


def register_socketio_events(socketio):
    """Register all Socket.IO event handlers."""

    @socketio.on('connect')
    def handle_connect():
        print(f'[SocketIO] Client connected')

    @socketio.on('disconnect')
    def handle_disconnect():
        # Clean up viewer from all streams
        for stream_id in list(stream_viewers.keys()):
            sid = getattr(current_user, 'id', None) or 'anon'
            if sid in stream_viewers.get(stream_id, set()):
                stream_viewers[stream_id].discard(sid)
                count = len(stream_viewers.get(stream_id, set()))
                emit('viewer_count', {'count': count}, room=f'stream_{stream_id}')

    # ─── Stream Room Management ─────────────────────────────────
    @socketio.on('join_stream')
    def handle_join_stream(data):
        stream_id = data.get('stream_id')
        room = f'stream_{stream_id}'
        join_room(room)

        # Track viewer
        if stream_id not in stream_viewers:
            stream_viewers[stream_id] = set()

        user_id = current_user.id if current_user.is_authenticated else f'anon_{id(data)}'
        stream_viewers[stream_id].add(user_id)
        count = len(stream_viewers[stream_id])

        # Notify everyone in room
        username = current_user.username if current_user.is_authenticated else 'Someone'
        emit('viewer_joined', {
            'username': username,
            'count': count
        }, room=room)

        # Update DB viewer count
        from models import db, LiveStream
        stream = LiveStream.query.get(stream_id)
        if stream:
            stream.viewer_count = count
            if count > stream.peak_viewers:
                stream.peak_viewers = count
            db.session.commit()

    @socketio.on('leave_stream')
    def handle_leave_stream(data):
        stream_id = data.get('stream_id')
        room = f'stream_{stream_id}'
        leave_room(room)

        user_id = current_user.id if current_user.is_authenticated else f'anon_{id(data)}'
        if stream_id in stream_viewers:
            stream_viewers[stream_id].discard(user_id)
        count = len(stream_viewers.get(stream_id, set()))

        username = current_user.username if current_user.is_authenticated else 'Someone'
        emit('viewer_left', {
            'username': username,
            'count': count
        }, room=room)

        from models import db, LiveStream
        stream = LiveStream.query.get(stream_id)
        if stream:
            stream.viewer_count = count
            db.session.commit()

    # ─── WebRTC Signaling ────────────────────────────────────────
    @socketio.on('webrtc_offer')
    def handle_offer(data):
        stream_id = data.get('stream_id')
        emit('webrtc_offer', {
            'offer': data.get('offer'),
            'stream_id': stream_id
        }, room=f'stream_{stream_id}', include_self=False)

    @socketio.on('webrtc_answer')
    def handle_answer(data):
        stream_id = data.get('stream_id')
        emit('webrtc_answer', {
            'answer': data.get('answer'),
            'stream_id': stream_id
        }, room=f'stream_{stream_id}', include_self=False)

    @socketio.on('webrtc_ice_candidate')
    def handle_ice_candidate(data):
        stream_id = data.get('stream_id')
        emit('webrtc_ice_candidate', {
            'candidate': data.get('candidate'),
            'stream_id': stream_id
        }, room=f'stream_{stream_id}', include_self=False)

    # Streamer sends their stream to new viewer
    @socketio.on('request_stream')
    def handle_request_stream(data):
        stream_id = data.get('stream_id')
        emit('new_viewer_request', {
            'requester_sid': data.get('requester_sid', ''),
            'stream_id': stream_id
        }, room=f'stream_{stream_id}')

    # ─── Live Chat ────────────────────────────────────────────────
    @socketio.on('chat_message')
    def handle_chat_message(data):
        stream_id = data.get('stream_id')
        message = data.get('message', '').strip()

        if not message or len(message) > 500:
            return

        username = 'Anonymous'
        avatar_letter = 'A'
        if current_user.is_authenticated:
            username = current_user.username
            avatar_letter = username[0].upper()

        emit('new_chat_message', {
            'username': username,
            'avatar': avatar_letter,
            'message': message,
            'time': datetime.utcnow().strftime('%H:%M')
        }, room=f'stream_{stream_id}')

    # ─── Stream Actions ───────────────────────────────────────────
    @socketio.on('end_stream_live')
    def handle_end_stream(data):
        stream_id = data.get('stream_id')
        emit('stream_ended', {
            'message': 'The streamer has ended this live stream.'
        }, room=f'stream_{stream_id}')

        # Clean up
        if stream_id in stream_viewers:
            del stream_viewers[stream_id]

    @socketio.on('heart_reaction')
    def handle_heart(data):
        stream_id = data.get('stream_id')
        username = current_user.username if current_user.is_authenticated else 'Someone'
        emit('heart_animation', {
            'username': username
        }, room=f'stream_{stream_id}')
