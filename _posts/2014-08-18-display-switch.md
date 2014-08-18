---
layout: post
title: "Display Switch"
description: ""
category: 
tags: []
---
{% include JB/setup %}

## Container之间的显示切换 ##

###  *背景*
### SurfaceFlinger
- SurfaceFlinger内部有一系列的Layer，这些Layer与应用程序的各个窗口对应
- SurfaceFlinger根据Layer的Z值将它们重叠，然后计算消隐，最后合成显示画面
- SurfaceFlinger中的Z值是由WindowManagerService设置的

### WindowManagerService
- WMS内部有一系列的WindowState，这些WindowState与应用程序的各个窗口对应
- WMS根据Activity的启动顺序、激活状态以及系统界面的状态决定窗口的前后位置
- WMS根据窗口的前后位置设置SurfaceFlinger中对应Layer的Z值

### *切换解决方案*
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

### 3 .修改WindowManagerService
- WMS的成员变量`mContainerAdjustment`保存当前Container的Z值调整值
- WMS设置SurfaceFlinger中的Z值时会在正常的Z值之上加上`mContainerAdjustment`

### 4. 修改WindowStateAnimator
- WindowStateAnimator的成员变量`mLastContainerAdjustment`保存上次刷新本窗口的Z值时`WMS.mContainerAdjustment`的值
- 设置Z值得代码位于WindowStateAnimator类的`createSurfaceLocked()`和`prepareSurfaceLocked()`函数中
- `createSurfaceLocked()`函数用于为窗口创建一个Surface，调用时：
	
		1. 获取WMS.mContainerAdjustment的值
		2. 将该值保存在mLastContainerAdjustment
		3. 设置窗口的Z值为会在mAnimLayer + WMS.mContainerAdjustment加上该值
- `prepareSurfaceLocked()` 函数用于刷新窗口的状态，调用时：
		
		1. 获取WMS.mContainerAdjustment的值
		2. 判断该值与mLastContainerAdjustment的值是否一样
		3. 如果一样则刷新Z值为mAnimLayer + WMS.mContainerAdjustment
		4. 更新mLastContainerAdjustment的值为WMS.mContainerAdjustment
#### 修改文件
- `/frameworks/base/services/java/com/android/server/wm/WindowManagerService.java`
- `/frameworks/base/services/java/com/android/server/wm/WindowStateAnimator.java`
- 不用修改相照应的`Android.mk`


##相关参考图极其解释##

![](https://github.com/condroid/condroid.github.com/blob/master/imgs/20140818display1.png?raw=true)  