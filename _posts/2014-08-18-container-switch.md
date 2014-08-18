---
layout: post
title: "Container Switch"
description: ""
category: 
tags: []
---
{% include JB/setup %}

## /dev/container设备 ##

### Device Drive
- /dev/container设备是一个虚拟设备，设备驱动代码位于内核`drivers/staging/android/container.c`
- container设备提供container的注册（表示已经启动）和切换的功能
- 通过对该设备进行ioctl操作可以完成指定的功能

### ioctl Operation
1. `CONTAINER_REGISTER`：参数为指向一个int的指针，用于注册该指针指向的Container的ID
2. `CONTAINER_GET_FRONT_ID`：参数为一个指向int的指针，调用后会写入当前活动的Container的ID
3. `CONTAINER_GET_STACK_POS`：参数为一个指向int的指针，调用前应填入需要获取位置的Container的ID，调用后会写入该Container在栈中的位置
4. `CONTAINER_SET_FRONT_ID`：参数为一个指向int的指针，用于将该指针指向的Container ID设置为活动的Container
5. `CONTAINER_WAIT_FOR_NEW_POS`：参数为一个指向int的指针，调用前应填入需要等待位置的Container的ID，调用后会写入该Container的新位置


## The Interface of Container

### C++ Interface
- C++层和Java层都对container设备的访问接口进行了封装  
- C++层的封装代码位于`frameworks/native/libs/container/Container.cpp`，编译生成`libcontainer.so`，接口定义如下：
	
		int getCurrentContainer(void)					获取当前进程所在的Container号
    	int registerContainer(int container)			注册一个Container号
	    int getFrontContainer(void)						获取前台的Container号
	    int isCurrentContainerTheFront(void)			判断当前Container是不是在前台
	    int getContainerPosition(int container)			获取Container在栈中的位置
	    int setFrontContainer(int container)			设置某个Container为前台的Container
	    int waitForNewPosition(int container)			使当前进入睡眠状态，直到指定的Container位置发生改变
		int getAvailableContainers(int containers[])	获取当前正在运行的所有Container的ID

### Java Interface
Java接口为android.util.Container类，源代码位于`/frameworks/base/core/java/android/util/Container.java`，通过JNI（代码位于`/frameworks/base/core/jni/android_util_Container.cpp`）访问C++接口

1. `int getCurrentContainer()`：返回当前进程所在的Container的ID
2. `int registerContainer(int container)`：注册一个Container ID，即通知内核该Container已经启动
3. `int getFrontContainer()`：返回当前活动的Container
4. `int setFrontContainer(int container)`：设置某个Container为活跃的Container
5. `int getContainerPosition(int container)`：获取某个Container的位置
6. `int waitForNewPosition(int container)`：调用后当前线程进入睡眠状态，直到指定的Container的位置被改变，返回该Container的新位置
7. `int registerCurrentContainer()`：注册当前进程所在的Container


## Container Switch

### IContainerManager
- IContainerManager是一个进程间通信的接口，定义了App与ContainerManagerService的通信协议，定义位于`frameworks/base/core/java/android/util/IContainerManager.aidl`
- IContainerManager定义的函数如下：
	
		int switchToContainer(int container)	切换到指定的container
    	int getCurrentContainer()				获取当前进程所在的container
    	int getFrontContainer()					获取前台的container
    	boolean isCurrentContainerInFront()		判断当前进程所在的container是否在前台
    	int[] getAvailableContainers()			获取当前正在运行的所有container

#### Modified files
- `/frameworks/base/core/java/android/util/IContainerManager.aidl`，文件添加
- `/frameworks/base/Android.mk`，中的`src_files`中添加，`/frameworks/base/core/java/android/util/IContainerManager.aidl`，这一行文字，如果希望该接口在sdk中开放，就在下面的aidl_files中也添加。

### ContainerManagerService
- CMS是一个服务，服务名为“container”，它实现了IContainerManager定义的所有功能，代码位于`frameworks/base/services/java/com/android/server/ContainerManagerService.java`
- CMS由SystemServer启动，在每个Container中都有
- 客户端可以通过Binder机制对CMS发起远程调用

#### Modified files
- `/frameworks/base/services/java/com/android/server/ContainerManagerService.java`,直接添加
- `/frameworks/base/servcies/java/com/android/server/SystemServer.java`,添加对ContainerManager的实例化和调用
- 对该目录修改会生成`system/frameworks/services.jar`

### ContainerManager SDK
- ContainerManager是CMS的客户端，代码位于development/containermanager，编译生成的jar包位于
		
		out/target/common/obj/JAVA_LIBRARIES/containermanager_intermediates/classes.jar
- ContainerManager通过远程调用CMS的接口函数来实现Container的查看和管理
- ContainerManager属于Android SDK的一部分，在App中调用ContainerManager的相关函数即可访问CMS提供的接口

### Container Switchover Process
1. 应用程序调用ContainerManager类的切换函数`switchToContainer(int)`
2. ContainerManager类通过Binder机制远程调用ContainerManagerService的`switchToContainer(int)`接口
3. ContainerManagerService调用container设备的Java接口，即`android.util.Container`类的`setFrontContainer(int)`函数
4. Java接口通过JNI调用C++接口，即libcontainer.so中Container类的`setFrontContainer(int)`函数
5. C++接口通过打开/dev/container设备，并对其进行`ioctl(CONTAINER_SET_FRONT_ID)`操作
6. container设备驱动接收到ioctl请求后更改container列表中各container的顺序，使得目标container位于最上层


##Reference Graph##

![](https://github.com/condroid/condroid.github.com/blob/master/imgs/20140818container1.png?raw=true)  