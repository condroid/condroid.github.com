---
layout: post
title: "Display Switch"
description: ""
category: 
tags: []
---
{% include JB/setup %}

## Container之间的显示切换 ##

###  *Background*
### SurfaceFlinger
- SurfaceFlinger内部有一系列的Layer，这些Layer与应用程序的各个窗口对应
- SurfaceFlinger根据Layer的Z值将它们重叠，然后计算消隐，最后合成显示画面
- SurfaceFlinger中的Z值是由WindowManagerService设置的

### WindowManagerService
- WMS内部有一系列的WindowState，这些WindowState与应用程序的各个窗口对应
- WMS根据Activity的启动顺序、激活状态以及系统界面的状态决定窗口的前后位置
- WMS根据窗口的前后位置设置SurfaceFlinger中对应Layer的Z值

### *Solution*
### 1. 为WMS添加ContainerThread
- ContainerThread代码位于 `frameworks/base/services/java/com/android/server/wm/WindowManagerService.java` ，是一个线程类
- ContainerThread创建时会调用`Container.registerContainer()`注册当前的Container
- ContainerThread线程运行时调用`Container.waitingForNewPosition()`等待当前Container的位置发生改变
- 当当前Container的位置发生变化时ContainerThread会发送一个消息给ContainerHandler

### 2. 为WMS添加ContainerHandler
- ContainerHandler代码位于`frameworks/base/services/java/com/android/server/wm/WindowManagerService.java`，是一个Handler类
- 当ContainerHandler接收到`CONTAINER_POSITION_CHANGED`消息时：
	
		1. 设置WMS的成员变量mContainerAdjustment，将其设置成当前Container的位置乘以1,000,000
		2. 调用WMS.scheduleAnimationLocked()刷新窗口的Z值

### 3 .Modify WindowManagerService
- WMS的成员变量`mContainerAdjustment`保存当前Container的Z值调整值
- WMS设置SurfaceFlinger中的Z值时会在正常的Z值之上加上`mContainerAdjustment`

### 4. Modify WindowStateAnimator
- WindowStateAnimator的成员变量`mLastContainerAdjustment`保存上次刷新本窗口的Z值时`WMS.mContainerAdjustment`的值
- 设置Z值的代码位于WindowStateAnimator类的`createSurfaceLocked()`和`prepareSurfaceLocked()`函数中
- `createSurfaceLocked()`函数用于为窗口创建一个Surface，调用时：
	
		1. 获取WMS.mContainerAdjustment的值
		2. 将该值保存在mLastContainerAdjustment
		3. 设置窗口的Z值为会在mAnimLayer + WMS.mContainerAdjustment加上该值
- `prepareSurfaceLocked()` 函数用于刷新窗口的状态，调用时：
		
		1. 获取WMS.mContainerAdjustment的值
		2. 判断该值与mLastContainerAdjustment的值是否一样
		3. 如果一样则刷新Z值为mAnimLayer + WMS.mContainerAdjustment
		4. 更新mLastContainerAdjustment的值为WMS.mContainerAdjustment
#### Modified files
- `/frameworks/base/services/java/com/android/server/wm/WindowManagerService.java`
- `/frameworks/base/services/java/com/android/server/wm/WindowStateAnimator.java`
- 不用修改相照应的`Android.mk`


##Reference Graph and explanation##

![](https://github.com/condroid/condroid.github.com/blob/master/imgs/20140818display1.png?raw=true)  

Linux Kernel中的Container device drive保存了当前各个container的前后顺序，当不同container进行切换时，如何在屏幕上及时准确地显示出来呢？

我们首先在WMS(WindowManagerService)借助ContainerThread，创建线程时注册当前的Container；线程运行时监测当前Container的位置是否发生改变，当前Container的位置发生变化时，ContainerThread会发送一个message给ContainerHandler；

ContainerHandler收到message后，将当前container的位置乘以1,000,000，新值赋给WMS的成员变量`mContainerAdjustment`；并刷新窗口的Z值；WMS设置SurfaceFlinger中的Z值时会在正常的Z值之上加上`mContainerAdjustment`；

通过WindowStateAnimator的成员变量`mLastContainerAdjustment`和`WMS.mContainerAdjustment`比较，并更新值。