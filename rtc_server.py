# -*- coding: utf-8 -*-

import time
from rtc import RtcServer, CvCapture


# here is example
if __name__ == "__main__":
    """
    对于RtcServer类,存在一个必须传入的对象cap
    该对象可为任何类型,但必须存在一个子方法：get_latest_frame
    该子方法返回一个元组：ret，frame
    ret为一个bool类型变量
    frame为CV2格式的图像
    port为本地sdp信令服务的开放端口。
    """

    cap = CvCapture(cam="/dev/video0", width=2560, height=720, fps=30)
    rtc_serv = RtcServer(cap=cap, port=20000)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print("exit with ctrl+c")
        del rtc_serv
