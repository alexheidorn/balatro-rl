import json
import logging
import os
import platform
from typing import Dict, Any, Optional


class BalatroPipeIO:
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.request_handle = None
        self.response_handle = None
        
        if platform.system() == "Windows":
            self.request_pipe = r'\\.\pipe\balatro_request'
            self.response_pipe = r'\\.\pipe\balatro_response'
        else:
            self.request_pipe = '/tmp/balatro_request'
            self.response_pipe = '/tmp/balatro_response'

        self.create_pipes()
        self.open_persistent_handles()

    def create_pipes(self) -> None:
        if platform.system() == "Windows":
            # On Windows, named pipes are created via Win32 API
            # We do this in open_persistent_handles using pywin32
            self.logger.info("Windows: pipes will be created as named pipe server")
            return
        
        # Linux/WSL: use mkfifo
        for pipe_path in [self.request_pipe, self.response_pipe]:
            try:
                if not os.path.exists(pipe_path):
                    os.mkfifo(pipe_path)
                    self.logger.info(f"Created pipe: {pipe_path}")
                else:
                    self.logger.info(f"Pipe already exists: {pipe_path}")
            except Exception as e:
                self.logger.error(f"Failed to create pipe {pipe_path}: {e}")
                raise RuntimeError(f"Could not create pipe: {pipe_path}")

    def open_persistent_handles(self) -> None:
        try:
            if platform.system() == "Windows":
                self._open_windows_pipes()
            else:
                self._open_unix_pipes()
        except Exception as e:
            self.logger.error(f"Failed to open persistent handles: {e}")
            self.cleanup_handles()
            raise RuntimeError(f"Could not open persistent pipe handles: {e}")

    def _open_windows_pipes(self):
        import msvcrt
        import pywintypes
        import win32pipe
        import win32file

        self.logger.info("Creating Windows named pipe servers...")
        self.logger.info("Press 'R' in Balatro now to activate RL training!")

        self._req_pipe_handle = win32pipe.CreateNamedPipe(
            self.request_pipe,
            win32pipe.PIPE_ACCESS_INBOUND,
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
            1, 65536, 65536, 0, None
        )

        self._res_pipe_handle = win32pipe.CreateNamedPipe(
            self.response_pipe,
            win32pipe.PIPE_ACCESS_OUTBOUND,
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
            1, 65536, 65536, 0, None
        )

        self.logger.info("Waiting for Balatro to connect to pipes...")
        win32pipe.ConnectNamedPipe(self._req_pipe_handle, None)
        win32pipe.ConnectNamedPipe(self._res_pipe_handle, None)
        self.logger.info("Balatro connected!")

        # Use msvcrt.open_osfhandle instead of the broken GetOSHandle approach
        req_fd = msvcrt.open_osfhandle(int(self._req_pipe_handle), os.O_RDONLY)
        res_fd = msvcrt.open_osfhandle(int(self._res_pipe_handle), os.O_WRONLY)
        self.request_handle = os.fdopen(req_fd, 'r', encoding='utf-8')
        self.response_handle = os.fdopen(res_fd, 'w', encoding='utf-8')

    def _open_unix_pipes(self):
        import threading

        self.logger.info("Waiting for Balatro to connect...")
        self.logger.info("Press 'R' in Balatro now to activate RL training!")

        req_fd = None
        res_fd = None

        def open_request():
            nonlocal req_fd
            req_fd = os.open(self.request_pipe, os.O_RDONLY)

        def open_response():
            nonlocal res_fd
            res_fd = os.open(self.response_pipe, os.O_WRONLY)

        # Open both ends concurrently to avoid blocking
        req_thread = threading.Thread(target=open_request)
        res_thread = threading.Thread(target=open_response)
        req_thread.start()
        res_thread.start()
        req_thread.join()
        res_thread.join()

        self.request_handle = os.fdopen(req_fd, 'r', encoding='utf-8')
        self.response_handle = os.fdopen(res_fd, 'w', encoding='utf-8')

    def wait_for_request(self) -> Optional[Dict[str, Any]]:
        if not self.request_handle:
            self.logger.error("Request handle not open")
            return None
        try:
            request_line = self.request_handle.readline().strip()
            if not request_line:
                return None
            request_data = json.loads(request_line)
            self.logger.debug(f"📥 RECEIVED: {request_line}")
            return request_data
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in request: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error reading from request pipe: {e}")
            return None

    def send_response(self, response_data: Dict[str, Any]) -> bool:
        if not self.response_handle:
            self.logger.error("Response handle not open")
            return False
        try:
            json.dump(response_data, self.response_handle)
            self.response_handle.write('\n')
            self.response_handle.flush()
            self.logger.debug(f"📤 SENT: {json.dumps(response_data)}")
            return True
        except Exception as e:
            self.logger.error(f"Error sending response: {e}")
            return False

    def cleanup_handles(self):
        for handle_name in ['request_handle', 'response_handle']:
            h = getattr(self, handle_name, None)
            if h:
                try:
                    h.close()
                except Exception:
                    pass
                setattr(self, handle_name, None)

        # Also close Windows PyHANDLE objects if they exist
        if platform.system() == "Windows":
            for handle_name in ['_req_pipe_handle', '_res_pipe_handle']:
                h = getattr(self, handle_name, None)
                if h:
                    try:
                        import win32file
                        win32file.CloseHandle(h)
                    except Exception:
                        pass
                    setattr(self, handle_name, None)

    def cleanup(self):
        self.cleanup_handles()
        if platform.system() != "Windows":
            for pipe_path in [self.request_pipe, self.response_pipe]:
                try:
                    if os.path.exists(pipe_path):
                        os.unlink(pipe_path)
                except Exception:
                    pass