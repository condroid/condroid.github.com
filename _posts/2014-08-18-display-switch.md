---
layout: post
title: "Display Switch"
description: ""
category: 
tags: []
---
{% include JB/setup %}

## Switch and Display between Containers ##

###  *Background*
### SurfaceFlinger
- SurfaceFlinger inside has a series of layers,which correspond to the windows of applications
- SurfaceFlinger overlaps the windows according to the Z value of layers,calculates the blanking and display the synthetic frames
- SurfaceFlinger's Z value is set by WindowManagerService

### WindowManagerService
- WMS inside has a series of WindowStates,which correspond to the windows of applications
- WMS decides the position of windows according to the startup sequence，activated state and system interface state
- WMS set the Z value of corresponding layer in SurfaceFlinger according to the windows's position

### *Solution*
### 1. Add ContainerThread for WMS
- ContainerThread code consists in `frameworks/base/services/java/com/android/server/wm/WindowManagerService.java`,which is a class of thread
- ContainerThread call `Container.registerContainer()` to register current container when created
- ContainerThread call `Container.waitingForNewPosition()` to wait for the change of current container's position while running
- When the position is changed,ContainerThread will send a message to ContainerHandler

### 2. Add ContainerHandler for WMS
- ContainerHandler code consists in `frameworks/base/services/java/com/android/server/wm/WindowManagerService.java`,which is a class of thread 
- When ContainerHandler receives `CONTAINER_POSITION_CHANGED` message:
	
		1. Set WMS's member variable-mContainerAdjustment as the current container's position * 1,000,000
		2. call WMS.scheduleAnimationLocked() to refresh Z value of windows

### 3 .Modify WindowManagerService
- `mContainerAdjustment`,WMS's member variable,is to save adjusted Z value of current container
- WMS set Z value of SurfaceFlinger;it will add `mContainerAdjustment` on the normal Z value 

### 4. Modify WindowStateAnimator
- `mLastContainerAdjustment`,WindowStateAnimator's member variable,is to save last value of `WMS.mContainerAdjustment`
- Code consists in function `createSurfaceLocked()` and `prepareSurfaceLocked()`of WindowStateAnimator class to set Z value
- function `createSurfaceLocked()` is to create a surface for windows,when calling:
	
		1. Get WMS.mContainerAdjustment's value
		2. Save it by mLastContainerAdjustment
		3. Set windows's Z value as mAnimLayer + WMS.mContainerAdjustment
- function `prepareSurfaceLocked()` is to refresh windows's state,when calling:
		
		1. Get WMS.mContainerAdjustment's value
		2. Judge the value,if it's same as mLastContainerAdjustment's value
		3. If the same,refresh Z value as mAnimLayer + WMS.mContainerAdjustment
		4. Update mLastContainerAdjustment's value as WMS.mContainerAdjustment
#### Modified files
- `/frameworks/base/services/java/com/android/server/wm/WindowManagerService.java`
- `/frameworks/base/services/java/com/android/server/wm/WindowStateAnimator.java`
- Don't need to modify relevant `Android.mk`


##Reference Graph and explanation##

![](https://github.com/condroid/condroid.github.com/blob/master/imgs/20140818display1.png?raw=true)  

Linux Kernel中的Container device drive保存了当前各个container的前后顺序，当不同container进行切换时，如何在屏幕上及时准确地显示出来呢？

我们首先在WMS(WindowManagerService)借助ContainerThread，创建线程时注册当前的Container；线程运行时监测当前Container的位置是否发生改变，当前Container的位置发生变化时，ContainerThread会发送一个message给ContainerHandler；

ContainerHandler收到message后，将当前container的位置乘以1,000,000，新值赋给WMS的成员变量`mContainerAdjustment`；并刷新窗口的Z值；WMS设置SurfaceFlinger中的Z值时会在正常的Z值之上加上`mContainerAdjustment`；

通过WindowStateAnimator的成员变量`mLastContainerAdjustment`和`WMS.mContainerAdjustment`比较，并更新值。