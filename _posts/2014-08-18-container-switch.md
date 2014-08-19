---
layout: post
title: "Container Switch"
description: ""
category: 
tags: []
---
{% include JB/setup %}

## /dev/container device ##

### Device Drive
- /dev/container device is a virtual one,device driver code is in `drivers/staging/android/container.c` in kernel
- Container device provide the function of register and switch for container
- By ioctl operating on the device,we can finish specified function

### ioctl Operation
1. `CONTAINER_REGISTER`:its parameter is a pointer to int;to register the container's ID to which the pointer points
2. `CONTAINER_GET_FRONT_ID`:parameter is a pointer to int;to write in running container's ID
3. `CONTAINER_GET_STACK_POS`:parameter is a pointer to int;to write in container's ID which need get position before calling;to write in the container's position in stack after calling
4. `CONTAINER_SET_FRONT_ID`:parameter is a pointer to int;to set the container's ID to which the pointer points active
5. `CONTAINER_WAIT_FOR_NEW_POS`:parameter is a pointer to int;to write in container's ID which need wait for position before calling;to write in the container's new position after calling


## The Interface of Container

### C++ Interface
- C++ layer and Java layer encapsulate the access interface of container device
- C++ layer's encapsulation code is in `frameworks/native/libs/container/Container.cpp`;it generates `libcontainer.so` from compilation；the definition of interface is as follow:
	
		int getCurrentContainer(void)					get container's ID in which current process is
    	int registerContainer(int container)			register a container's ID
	    int getFrontContainer(void)						judge the container's ID in front
	    int isCurrentContainerTheFront(void)			judge the container's ID if is in front
	    int getContainerPosition(int container)			get the container's position in stack
	    int setFrontContainer(int container)			set a container in front
	    int waitForNewPosition(int container)			make current process sleep until specified container's position changes
		int getAvailableContainers(int containers[])	get all running containers' ID

### Java Interface
Java Interface is a kind of android.util.Container class;its source code is in `/frameworks/base/core/java/android/util/Container.java`;it accesses C++ Interface by JNI（its code is in `/frameworks/base/core/jni/android_util_Container.cpp`）

1. `int getCurrentContainer()`:return the ID of container in which current process is
2. `int registerContainer(int container)`:register a container ID to tell kernel the container has started
3. `int getFrontContainer()`:return the present active container
4. `int setFrontContainer(int container)`:set a container active
5. `int getContainerPosition(int container)`:get the position of a container
6. `int waitForNewPosition(int container)`:current process stay sleep after calling;until specified container's position changes,it'll return the container's new position
7. `int registerCurrentContainer()`:register the container in which current process is


## Container Switch

### IContainerManager
- IContainerManager is a interface of inter-process communication,which defines the communication protocol between App and ContainerMana;and the definition is in `frameworks/base/core/java/android/util/IContainerManager.aidl`
- Functions which IContainerManager defines as follow:
	
		int switchToContainer(int container)	switch to specified container
    	int getCurrentContainer()				get container in which current process is
    	int getFrontContainer()					get the front-end container
    	boolean isCurrentContainerInFront()		judge the container in which current process is if front-end
    	int[] getAvailableContainers()			get all running containers

#### Modified files
- Add file `/frameworks/base/core/java/android/util/IContainerManager.aidl`
- In `/frameworks/base/Android.mk`,`src_files` add line `/frameworks/base/core/java/android/util/IContainerManager.aidl`;if you hope the interface is open for sdk，add it in following file `aidl_files`

### ContainerManagerService
- CMS is a service,whose name is "container";it realized all functions IContainerManager defines,AMS's code is in `frameworks/base/services/java/com/android/server/ContainerManagerService.java`
- CMS is started by SystemServer,and consists in every container
- Client can  make remote calls to CMS by Binder mechanism

#### Modified files
- Add file `/frameworks/base/services/java/com/android/server/ContainerManagerService.java`
- `/frameworks/base/servcies/java/com/android/server/SystemServer.java`,add instantiation and call to ContainerManager
- Modify this catalogue and it will generate `system/frameworks/services.jar`

### ContainerManager SDK
- ContainerManager is a client of CMS;its code is in development/contain and it generates ermanager;generated jar package from compilation is in
		
		out/target/common/obj/JAVA_LIBRARIES/containermanager_intermediates/classes.jar
- ContainerManager realize the check and management by remote calls to CMS's interface function
- ContainerManager belongs to Android SDK;it calls relevant functions in App to access interfaces CMS provides

### Container Switchover Process
1. Applications call switching function-`switchToContainer(int)` of ContainerManager class
2. ContainerManager class makes remote calls to `switchToContainer(int)` interface of ContainerManagerService by Binder mechanism
3. ContainerManagerService calls Java interface of container device;that is `setFrontContainer(int)` function of `android.util.Container` class
4. Java interface calls C++ interface by JNI;that is `setFrontContainer(int)` function of container  in libcontainer.so
5. C++ interface open /dev/container device,and do `ioctl(CONTAINER_SET_FRONT_ID)` operation on it
6. Container device driver updates the sequence in container list after receiving ioctl operation to make the target container top


##Reference Graph##

![](https://github.com/condroid/condroid.github.com/blob/master/imgs/20140818container1.png?raw=true)  