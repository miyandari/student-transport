
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:

    def __init__(self):

        self.active_connections: dict[
            int,
            set[WebSocket]
        ] = defaultdict(set)


    async def connect(
        self,
        trip_id: int,
        websocket: WebSocket,
    ) -> None:

        # اتصال قبلاً در WebSocket endpoint پذیرفته شده است.
        # بنابراین اینجا نباید دوباره websocket.accept() اجرا شود.

        self.active_connections[trip_id].add(
            websocket
        )


    def disconnect(
        self,
        trip_id: int,
        websocket: WebSocket,
    ) -> None:

        connections = self.active_connections.get(
            trip_id
        )

        if not connections:
            return

        connections.discard(websocket)

        if not connections:

            self.active_connections.pop(
                trip_id,
                None
            )


    async def send_to_trip(
        self,
        trip_id: int,
        message: dict,
    ) -> None:

        connections = self.active_connections.get(
            trip_id
        )

        if not connections:
            return

        disconnected_connections = set()

        for websocket in connections:

            try:

                await websocket.send_json(
                    message
                )

            except Exception:

                disconnected_connections.add(
                    websocket
                )


        for websocket in disconnected_connections:

            self.disconnect(
                trip_id,
                websocket
            )


    def get_connection_count(
        self,
        trip_id: int,
    ) -> int:

        return len(
            self.active_connections.get(
                trip_id,
                set()
            )
        )


connection_manager = ConnectionManager()
