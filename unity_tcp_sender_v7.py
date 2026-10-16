# unity_tcp_sender_v7.py
# ============================================================
# TCP JSON sender to Unity
#
# Supported message types:
#
# 1) Face / motion data:
# {
#   "type": "face_data",
#   "roll": ...,
#   "yaw": ...,
#   "lip_open_dist_3d": ...,
#   "mouth_width_dist_3d": ...,
#   "upper_lip_thickness_3d": ...,
#   "lower_lip_thickness_3d": ...
# }\n
#
# 2) Speech text:
# {
#   "type": "speech_text",
#   "job_id": ...,
#   "text": "..."
# }\n
#
# 3) Clear speech text:
# {
#   "type": "speech_text_clear"
# }\n
#
# 4) Person detection:
# {
#   "type": "person_detection",
#   "person_detected": true/false,
#   "person_id": ...,
#   "person_name": "...",
#   "confidence": ...,
#   "bbox_x": ...,
#   "bbox_y": ...,
#   "bbox_w": ...,
#   "bbox_h": ...,
#   "center_x": ...,
#   "center_y": ...,
#   "meta": {...}
# }\n
#
# 5) Microphone state:
# {
#   "type": "microphone_state",
#   "mic_on": true/false,
#   "state": "ON"/"OFF",
#   "reason": "...",
#   "session_id": "...",
#   "turn_id": "...",
#   "meta": {...}
# }\n
# ============================================================

from __future__ import annotations

import json
import socket
import threading
from typing import Any, Dict, Optional


class UnityTcpServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 5005):
        self.host = host
        self.port = port
        self.server: Optional[socket.socket] = None
        self.conn: Optional[socket.socket] = None
        self.addr = None
        self._send_lock = threading.Lock()
        self._v17_person_present = False

    def start_and_wait_for_client(self) -> None:
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(1)

        print(f"[TCP] Waiting Unity connection on {self.host}:{self.port} ...")
        self.conn, self.addr = self.server.accept()
        print(f"[TCP] Unity connected: {self.addr}")

    def _ensure_connected(self) -> None:
        if self.conn is None:
            raise RuntimeError("Unity client is not connected.")

    def _send_json(self, data: Dict[str, Any]) -> None:
        self._ensure_connected()
        msg = json.dumps(data, ensure_ascii=False) + "\n"
        encoded = msg.encode("utf-8")

        with self._send_lock:
            self.conn.sendall(encoded)

    def send_face_data(
        self,
        roll: float,
        yaw: float,
        lip_open_dist_3d: float,
        mouth_width_dist_3d: float,
        upper_lip_thickness_3d: float,
        lower_lip_thickness_3d: float,
    ) -> None:
        data = {
            "type": "face_data",
            "roll": float(roll),
            "yaw": float(yaw),
            "lip_open_dist_3d": float(lip_open_dist_3d),
            "mouth_width_dist_3d": float(mouth_width_dist_3d),
            "upper_lip_thickness_3d": float(upper_lip_thickness_3d),
            "lower_lip_thickness_3d": float(lower_lip_thickness_3d),
        }
        self._send_json(data)

    def send_speech_text(self, text: str, job_id: Optional[int] = None) -> None:
        data = {
            "type": "speech_text",
            "job_id": int(job_id) if job_id is not None else -1,
            "text": str(text),
        }
        self._send_json(data)

    def send_clear_speech_text(self) -> None:
        data = {
            "type": "speech_text_clear"
        }
        self._send_json(data)

    def send_person_detection(
        self,
        person_detected: bool,
        person_id: int = -1,
        person_name: str = "",
        confidence: float = 0.0,
        bbox_x: float = 0.0,
        bbox_y: float = 0.0,
        bbox_w: float = 0.0,
        bbox_h: float = 0.0,
        center_x: float = 0.0,
        center_y: float = 0.0,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self._v17_person_present and not person_detected:
            self.send_clear_speech_text()
        self._v17_person_present = bool(person_detected)
        data = {
            "type": "person_detection",
            "person_detected": bool(person_detected),
            "person_id": int(person_id),
            "person_name": str(person_name),
            "confidence": float(confidence),
            "bbox_x": float(bbox_x),
            "bbox_y": float(bbox_y),
            "bbox_w": float(bbox_w),
            "bbox_h": float(bbox_h),
            "center_x": float(center_x),
            "center_y": float(center_y),
            "meta": meta if meta is not None else {},
        }
        self._send_json(data)

    def send_microphone_state(
        self,
        mic_on: bool,
        reason: str = "",
        session_id: str = "",
        turn_id: str = "",
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send microphone ON/OFF state to Unity.

        Meaning:
        - mic_on=True:
            Python is ready to listen/record user speech.
        - mic_on=False:
            Python should not accept microphone input because it is playing audio,
            processing, waiting, or no active session is available.

        Suggested reasons:
        - "ready_to_record"
        - "no_active_session"
        - "playing_greeting_audio"
        - "recording_finished"
        - "processing_after_record"
        - "speech_to_text"
        - "playing_waiting_audio"
        - "playing_response_audio"
        - "runtime_shutdown"
        """
        data = {
            "type": "microphone_state",
            "mic_on": bool(mic_on),
            "state": "ON" if mic_on else "OFF",
            "reason": str(reason),
            "session_id": str(session_id),
            "turn_id": str(turn_id),
            "meta": meta if meta is not None else {},
        }
        self._send_json(data)

    def send_message(self, data: Dict[str, Any]) -> None:
        """
        Generic JSON sender for future extension.
        Caller is responsible for providing a valid JSON-ready dict.
        """
        self._send_json(data)

    def close(self) -> None:
        try:
            if self.conn is not None:
                self.conn.close()
        finally:
            self.conn = None

        try:
            if self.server is not None:
                self.server.close()
        finally:
            self.server = None


if __name__ == "__main__":
    tcp = UnityTcpServer(host="127.0.0.1", port=5005)

    try:
        tcp.start_and_wait_for_client()

        # Example face packet
        tcp.send_face_data(
            roll=-12.5,
            yaw=8.3,
            lip_open_dist_3d=0.42,
            mouth_width_dist_3d=1.15,
            upper_lip_thickness_3d=0.18,
            lower_lip_thickness_3d=0.21,
        )
        print("[TCP] Sent one face_data packet to Unity.")

        # Example speech text packet
        tcp.send_speech_text(
            text="Xin chào bạn. Tôi là trợ lý ảo.",
            job_id=1,
        )
        print("[TCP] Sent one speech_text packet to Unity.")

        # Example person detection packet
        tcp.send_person_detection(
            person_detected=True,
            person_id=1,
            person_name="TargetPerson",
            confidence=0.94,
            bbox_x=120,
            bbox_y=80,
            bbox_w=220,
            bbox_h=420,
            center_x=230,
            center_y=290,
            meta={"source": "detector_v1"}
        )
        print("[TCP] Sent one person_detection packet to Unity.")

        # Example microphone ON packet
        tcp.send_microphone_state(
            mic_on=True,
            reason="ready_to_record",
            session_id="test_session_001",
            turn_id="",
            meta={"source": "manual_test"}
        )
        print("[TCP] Sent one microphone_state ON packet to Unity.")

        # Example microphone OFF packet
        tcp.send_microphone_state(
            mic_on=False,
            reason="playing_response_audio",
            session_id="test_session_001",
            turn_id="turn_001",
            meta={"source": "manual_test"}
        )
        print("[TCP] Sent one microphone_state OFF packet to Unity.")

    except KeyboardInterrupt:
        print("\n[TCP] Stopped by user.")

    finally:
        tcp.close()
        print("[TCP] Closed.")