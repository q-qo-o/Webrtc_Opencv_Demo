import asyncio
import json
import cv2
import threading
import time
import socket
import numpy


from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaStreamError
from aiortc.rtcrtpsender import RTCRtpSender

from av import VideoFrame


"""
                  ,~^^```"~-,,<```.`;smm#####m,
              ,^  ,s###MT7;#M ]Q#` ,a###########M"`````'``"~-,
             /   "^^\  *W"3@"  ||  ~'7#######"\                '".
          :"          a ,##\         ]######               e#######M
         L         ,######~        ,#######              ############m
        f         ]######b         #######,           ,,##############b
       ;         .%#####J W####Mm, #####b    ,;,ap ,###################p
       ~ @#Q|^5mg##8#####  %#""Wgs#######T `@#mw,s#@#@########WW@#######
      ,^  ^= .MT\ j###C            @#@##"    `we"|   @#####b` ,m 3######
     ;    ,      #####      p   ,###,#"    .      ,######## ###m  ######
     ,%""Y"   ,]#",##\    `|p  @##,###M"1^3`   ;##########Q]##`  @######
    [     7W  ##,#### @m,   ^1 #######m#mw,@m  \@########C^|`.;s#######`
     y@Mw,   "#######C  ^"     |5###### mm ^"~ ,#########  ;##########`
    ^   ,aQ   ^@#####       N   ^j###7  `     ,######################
   D   #####mg,######      M##p   ##b     ,##################^,#####
   [   ##############       ##########m,###################, ;#####
    o  ^############       @##########M`^`~"%############"  @#####b
      "m,j#########b      @#######M|          @#######M"^^
          ,^^"||^7^"7\.   "#####"              \#M7|
                           "||`

         Karl Marx     Friedrich Engels     Vladimir Lenin
         
        基于asyio与threading实现的webrtc图传。       
"""


# 获取本地地址
def get_host_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # 随便连一个ip用来抓包
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip


# 强制视频编码
def force_codec(pc, sender, forced_codec):
    kind = forced_codec.split("/")[0]
    codecs = RTCRtpSender.getCapabilities(kind).codecs
    transceiver = next(t for t in pc.getTransceivers() if t.sender == sender)
    transceiver.setCodecPreferences(
        [codec for codec in codecs if codec.mimeType == forced_codec]
    )


# sdp服务器，基于udp提供sdp信令交换
class SdpServer:
    def __init__(self, udp_port: int):
        self.__udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__udp_socket.bind(("0.0.0.0", udp_port))

        self.__local_description = None
        self.__remote_description = None
        self.__remote_heart_beat = None

        self.__rev_handle_thread = threading.Thread(
            target=self.__recv_handle, args=(), daemon=True
        )
        self.__rev_handle_thread.start()
        print("SdpServer opened on %s port is %d" % (str(get_host_ip()), udp_port))

    def set_local_description(self, sdp: str):
        self.__local_description = sdp

    def get_remote_description(self):
        return self.__remote_description

    def get_remote_heart_beat(self):
        return self.__remote_heart_beat

    async def wait_remote_description(self):
        while self.__remote_description is None:
            await asyncio.sleep(0.1)

    def clear_connect_info(self):
        self.__local_description = None
        self.__remote_description = None
        self.__remote_heart_beat = None

    def __recv_handle(self):
        while True:
            remote_msg, remote_address = self.__udp_socket.recvfrom(4096)
            remote_msg = remote_msg.decode()

            if self.__local_description is not None:
                if remote_msg == "ask_offer":  # 返回邀请sdp
                    offer_json = {"type": "offer", "sdp": self.__local_description}
                    offer_data = json.dumps(offer_json).encode()
                    self.__udp_socket.sendto(offer_data, remote_address)
                elif remote_msg == "heart_beat":
                    self.__remote_heart_beat = time.time()
                else:
                    # 处理回复
                    answer_json = None
                    try:
                        answer_json = json.loads(remote_msg)
                    except:
                        pass
                    if (
                        answer_json is not None
                        and "sdp" in answer_json
                        and "type" in answer_json
                    ):
                        if answer_json["type"] == "answer":
                            self.__remote_description = answer_json["sdp"]

    def __del__(self):
        self.__rev_handle_thread.join()
        self.__udp_socket.close()


# 摄像头捕获
class CvCapture:
    def __init__(
        self, cam: int = 0, width: int = 1280, height: int = 720, fps: int = 30
    ) -> None:
        self.__cap = cv2.VideoCapture(cam)

        self.__cap.set(6, cv2.VideoWriter_fourcc("M", "J", "P", "G"))  # 视频流格式
        self.__cap.set(5, fps)  # 帧率
        self.__cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)  # 设置宽度
        self.__cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)  # 设置高度

        self.__latest_frame = numpy.zeros((height, width, 3), numpy.uint8).fill(255)
        self.__ret = False

        self.__capture_thread = threading.Thread(
            target=self.__CaptureThread, args=(), daemon=True
        )
        self.__capture_thread.start()

        # 等待摄像头启动
        cnt = 0
        while not self.get_latest_frame()[0]:
            time.sleep(0.1)
            cnt += 1
            if cnt * 0.1 > 3:
                print("似乎不存在摄像头ヽ(￣ω￣〃)ゝ")
                break
        if self.get_latest_frame()[0] is not None:
            print(
                "Cam %s opened. width:%d height:%d fps%d codec:mjpg"
                % (str(cam), width, height, fps)
            )

    def __CaptureThread(self):
        while True:
            s, frame = self.__cap.read()
            if s:
                self.__latest_frame = frame
                if not self.__ret:
                    self.__ret = True

    def get_latest_frame(self):
        return self.__ret, self.__latest_frame

    def __del__(self):
        self.__capture_thread.join()
        self.__cap.release()


# 对VideoStreamTrack的recv方法的覆盖
class CvStreamTrack(VideoStreamTrack):
    kind = "video"

    def __init__(self, cap: CvCapture, cli_fps=False):
        super().__init__()
        self.__cap = cap
        self.__cli_fps = cli_fps

        self.__end_time = 0

    async def recv(self):
        start_time = time.time()
        timestamp, video_timestamp_base = await self.next_timestamp()

        s, frame = self.__cap.get_latest_frame()
        if not s:
            return
        elif self.__cli_fps:
            fps = 1 / (start_time - self.__end_time)
            print("FPs: %.1f fps    " % fps, end="\r")

        frame = VideoFrame.from_ndarray(frame, format="bgr24")
        frame.pts = timestamp
        frame.time_base = video_timestamp_base

        self.__end_time = start_time
        return frame


# rtc视频服务器
class RtcServer:
    """
    对于RtcServer类,存在一个必须传入的对象cap
    该对象可为任何类型,但必须存在一个子方法：get_latest_frame
    该子方法返回一个元组：ret，frame
    ret为一个bool类型变量
    frame为CV2格式的图像
    port为本地sdp信令服务的开放端口。
    """

    def __init__(
        self,
        cap: CvCapture,
        port: int = 20000,
        codec: str = "video/Vp8",
    ) -> None:
        self.__codec = codec
        self.__pcs = set()
        self.__pc = RTCPeerConnection()
        self.__pcs.add(self.__pc)

        self.__cap = cap
        self.__sdp_serv = SdpServer(port)

        self.__rtc_server_thread = threading.Thread(
            target=self.__server, args=(), daemon=True
        )
        self.__rtc_server_thread.start()

    def __server(self):
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.__server_run())

    async def __server_run(self):

        @self.__pc.on("connectionstatechange")
        async def on_connectionstatechange():
            print("Connection state is %s" % self.__pc.connectionState)
            if self.__pc.connectionState == "failed":
                await self.__pc.close()
                self.__pcs.discard(self.__pc)
            if self.__pc.connectionState == "closed":
                self.__sdp_serv.clear_connect_info()

        def add_track():
            video_stream = self.__pc.addTrack(
                CvStreamTrack(cap=self.__cap, cli_fps=False)
            )
            force_codec(self.__pc, video_stream, self.__codec)
            print("Use %s" % self.__codec)

        async def wait_to_end():
            while self.__sdp_serv.get_remote_description() is not None:
                if self.__sdp_serv.get_remote_heart_beat() is not None:
                    if time.time() - self.__sdp_serv.get_remote_heart_beat() > 5:
                        await self.__pc.close()
                await asyncio.sleep(1)

        # 等待答复
        while True:

            add_track()
            offer = await self.__pc.createOffer()
            await self.__pc.setLocalDescription(offer)
            self.__sdp_serv.set_local_description(self.__pc.localDescription.sdp)

            print("Waiting for answer ...")
            await self.__sdp_serv.wait_remote_description()

            remote_description = self.__sdp_serv.get_remote_description()
            answer = RTCSessionDescription(sdp=remote_description, type="answer")
            await self.__pc.setRemoteDescription(answer)

            await wait_to_end()
            self.__pc = RTCPeerConnection()
            self.__pcs.add(self.__pc)

    def __del__(self):
        self.__rtc_server_thread.join()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.__pc.close())
        del self.__cap
        del self.__sdp_serv


class CvStream:
    def __init__(self, gui=False):
        self.__track = None
        self.__track_task = None

        self.__gui = gui

        import numpy as np

        self.__ret = False
        self.fps = 0
        self.__latest_frame = np.zeros((720, 1280, 3), np.uint8).fill(255)
        self.start_time = time.time()
        self.end_time = self.start_time

    def addTrack(self, track: VideoStreamTrack):
        if track.kind == "video":
            if self.__track_task is not None:
                self.__track_task.cancel()
            self.__track = track
            self.__track_task = None

    async def start(self):
        if self.__track is not None and self.__track_task is None:
            self.__track_task = asyncio.ensure_future(self.__run_track(self.__track))

    async def stop(self):
        if self.__track_task is not None:
            await self.__track_task.cancel()
        self.__track = None
        self.__track_task = None

    async def __run_track(self, track: VideoStreamTrack):
        while True:
            try:
                self.start_time = time.time()
                frame = await track.recv()
                self.__latest_frame = frame = frame.to_ndarray(format="bgr24")
                if self.__gui and self.__ret:
                    cv2.imshow("client", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        return
                self.__ret = True

                self.fps = 1 / (-self.end_time + self.start_time)
                print("FPs: %.1f fps    " % self.fps, end="\r")

                self.end_time = self.start_time

            except MediaStreamError:
                return

    def get_latest_frame(self):
        return self.__ret, self.__latest_frame


class RtcClient:
    """
    local_port用于指定开放的本地端口
    server_address用于指定服务端sdp信令服务的地址和端口
    cv_gui用于指示是否使用cv2.imshow展示图像
    """

    def __init__(
        self,
        local_port: int = 20001,
        server_address: tuple[str, int] = ("127.0.0.1", 20000),
        cv_gui: bool = False,
    ) -> None:

        self.__server_address = server_address

        local_address = (str(get_host_ip()), local_port)
        self.__udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__udp_socket.bind(local_address)
        print("local ip : %s local port is %d" % local_address)

        self.__pcs = set()
        self.__pc = RTCPeerConnection()
        self.__pcs.add(self.__pc)

        self.__cv_gui = cv_gui
        self.__cv_stream = CvStream(gui=cv_gui)

        self.__rtc_client_thread = threading.Thread(
            target=self.__client, args=(), daemon=True
        )
        self.__rtc_client_thread.start()

    def __client(self):
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.__run_client())

    async def __run_client(self):
        @self.__pc.on("connectionstatechange")
        async def on_connectionstatechange():
            print("Connection state is %s" % self.__pc.connectionState)
            if self.__pc.connectionState == "failed":
                await self.__pc.close()
                self.__pcs.discard(self.__pc)

        @self.__pc.on("track")
        def on_track(track):
            print("Receiving %s" % track.kind)
            self.__cv_stream.addTrack(track)

        # 请求offer
        while True:
            self.__udp_socket.sendto(
                "ask_offer".encode(), self.__server_address
            )  # 发送请求
            offer_data, _ = self.__udp_socket.recvfrom(4096)

            offer_json = None
            try:
                offer_json = json.loads(offer_data.decode())
            except:
                pass
            if offer_json is not None and offer_json["type"] == "offer":
                offer = RTCSessionDescription(sdp=offer_json["sdp"], type="offer")
                break
            else:
                print("Invalid offer type")

        await self.__pc.setRemoteDescription(offer)

        # 创建回复
        answer = await self.__pc.createAnswer()
        answer_date = json.dumps({"type": "answer", "sdp": answer.sdp})
        self.__udp_socket.sendto(answer_date.encode(), self.__server_address)
        await self.__pc.setLocalDescription(answer)

        await self.__cv_stream.start()

        while True:
            self.__udp_socket.sendto(
                "heart_beat".encode(), self.__server_address
            )  # 发送心跳
            await asyncio.sleep(1)

    def get_latest_frame(self):
        return self.__cv_stream.get_latest_frame()

    def __del__(self):
        self.__rtc_client_thread.join()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.__cv_stream.stop())
        loop.run_until_complete(self.__pc.close())
        if self.__cv_gui:
            cv2.destroyAllWindows()
