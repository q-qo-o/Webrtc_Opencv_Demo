# -*- coding: utf-8 -*-

import cv2
from rtc import RtcClient

# here is example
if __name__ == "__main__":
    '''
    local_port用于指定开放的本地端口
    server_address用于指定服务端sdp信令服务的地址和端口
    cv_gui用于指示是否使用cv2.imshow展示图像
    '''
    cl = RtcClient(
        local_port=20001, server_address=("192.168.2.176", 20000), cv_gui=False
    )

    try:
        while True:
            ret, frame = cl.get_latest_frame()
            if ret:
                cv2.imshow("client", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    except KeyboardInterrupt:
        pass
    finally:
        print("client exit")
        del cl

