# Webrtc Opencv Demo

为结合opencv与webrtc使用，基于upd、aiortc、pyav、opencv-python 封装了一些代码。

单个服务器只能连接一个客户端。

此处的requirements.txt仅供参考。

## 服务端使用

在`import RtcServer`后即可通过RtcServer建立一个服务器对象。该服务器对象开放了一个端口如`port=20000`用于实现与客户端交换SDP。同时该服务器对象需要传入一个摄像机捕获对象，此摄像机捕获对象需存在一个子方法`get_latest_frame`，该子方法返回一个元组：`tuple[ret，frame]`  ，其中` ret`为一个`bool`类型变量，`frame`为CV2格式的图像。

示例如下：

```python
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
```

## 客户端使用

在`import RtcClient`后即可通过`RtcClient`建立一个客户端对象。该客户端对象开放了一个端口`local_port=20001`，同时需要使用一个格式为`tuple[str,int]`的元组指定服务端地址与开放的端口。可以使用选项`cv_gui=`指定是否使用`cv2.imshow()`展示接收图像。

使用`get_latest_frame()`返回一个元组，格式为`tuple[ret，frame]` ，`ret`用于指示获取的图像是否有效，`frame`为获取的最新一帧图像。

示例如下：

```python
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
```

