---
layout: post
title: "Binder IPC Mechanism Multiplexing"
description: ""
category: 
tags: []
---
{% include JB/setup %}

所谓复用Binder IPC机制，是指Binder IPC机制的核心组件(如Binder设备驱动、Service Manager)由主机提供。虚拟机没有这些组件，虚拟机中的进程通过一个虚拟设备间接地使用主机提供Binder IPC机制。

虚拟机更好地使用主机提供的Binder IPC机制，在安全和性能之间找到一个平衡点。我们在虚拟机中使用虚拟Binder设备而非实际的Binder设备。

###技术方案
**1.构建虚拟Binder设备驱动**

我们在Android系统的Linux内核中添加了虚拟Binder设备的驱动程序，这个驱动程序的主要功能有以下两个方面：

(1)调用Binder设备驱动的函数，将应用程序对虚拟Binder设备的操作（如open, ioctl, mmap等）转发给真实的Binder设备驱动。

(2)拦截应用程序对虚拟Binder设备的ioctl操作，过滤出发送给Service Manager的注册服务（由服务进程发起）和获取服务（由客户端进程发起）的请求，并且在转发给真实Binder设备之前使用一个转换函数 f 修改这两种请求中的服务名字段。

转发设备操作使得虚拟Binder设备具有与真实Binder设备相同的功能。修改注册服务请求，使不同的虚拟机中运行的同名服务以不同的名字注册到主机的Service Manager中，解决名字冲突的问题。修改获取服务请求使得虚拟机中运行的客户端进程能够获取到与其运行在同一虚拟机中的服务，解决运行在不同虚拟机的同名服务之间无法区分的问题。

**2.创建和分配虚拟Binder设备**

驱动程序构建完成之后，我们在Linux内核初始化时使用这个驱动注册一组虚拟Binder设备，内核启动之后将自动创建这一组设备对应的设备文件。在虚拟机启动之前，我们将虚拟机根文件系统中的Binder设备文件（/dev/binder）与主机的某个虚拟Binder设备文件绑定。这样虚拟机中的程序访问其根文件系统中的/dev/binder相当于访问主机的虚拟Binder设备，即其访问操作将调用虚拟Binder设备驱动中的函数。

**3.实现共享服务列表**

由于Android设备的资源有限，而在一个设备上运行多个Android系统必然降低单个系统的运行性能。为了最大限度地减少Android虚拟化带来的性能损失，我们将一些可以被多个虚拟机共享的服务运行在主机中，而虚拟机中则不启动这些服务，然后通过设置共享服务列表来实现服务共享的功能，以此减少整个设备上运行的服务总数。为此，我们在proc文件系统中创建一个文件作为设置共享服务的接口，用户只需将服务名字写入这个文件就可以设置某个特定的服务为共享服务。所有共享服务的名字构成一个列表，保存在内核内存空间中。虚拟Binder设备驱动在修改注册服务和获取服务的请求时首先会查找这个列表。如果服务名字不在共享服务列表中则按照既定规则进行修改，否则不作修改，直接将请求转发给真实的Binder设备驱动。这样虚拟机中的客户端进程获取共享服务时得到的将是主机中运行的服务，虚拟机中则不运行这些服务。

###具体实施方法
**1.构建虚拟Binder设备驱动**

![](https://github.com/condroid/condroid.github.com/blob/master/imgs/20140814binder2.png)  

虚拟Binder设备驱动主要负责拦截、过滤和修改进程对Binder设备的各种操作，然后将操作请求转发给真实的Binder设备驱动。该驱动按照misc设备驱动的模型编写，代码存放在conbinder.c中。首先需要创建一个struct file_operations类型的结构体变量conbinder_fops，这个结构体中的函数指针与虚拟Binder设备的各种操作一一对应。我们对于需要拦截的操作编写自定义的驱动函数，对于不需要拦截的操作则直接使用真实Binder设备驱动中的函数。这些函数的实现方式如下表所示：

<table>
   <tr>
      <td><strong>对设备的操作</td>
      <td><strong>函数指针</td>
      <td><strong>实现方式</td>
   </tr>

   <tr>
      <td>打开Binder设备</td>
      <td>.open</td>
      <td>使用binder_open函数</td>

   </tr>

   <tr>
      <td>查询Binder设备是否可以非阻塞地读</td>
      <td>.poll</td>
      <td>使用binder_poll函数</td>
   </tr>

   <tr>
      <td>给Binder设备发送命令</td>
      <td>.unlocked_ioctl</td>
      <td>自定义conbinder_ioctl函数</td>
   </tr>

   <tr>
      <td>同上，用于64位系统中的32位进程</td>
      <td>.compact_ioctl</td>
      <td>自定义conbinder_ioctl函数</td>
   </tr>

   <tr>
      <td>将Binder设备的一段内存空间映射到进程的地址空间</td>
      <td>.mmap</td>
      <td>使用binder_mmap函数</td>
   </tr>

   <tr>
      <td>强制执行已缓冲的I/O操作</td>
      <td>.flush</td>
      <td>使用binder_flush函数</td>
   </tr>

   <tr>
      <td>释放Binder设备</td>
      <td>.release</td>
      <td>使用binder_release函数</td>
   </tr>
</table>



**2.创建和分配虚拟Binder设备**

![](https://github.com/condroid/condroid.github.com/blob/master/imgs/20140814binder2.png)  

为了使内核启动完成之后创建一组虚拟Binder设备，我们编写了conbinder_init函数用于初始化虚拟Binder设备的信息以及注册这些设备。首先我们定义了一组struct miscdevice类型的结构体，然后在conbinder_init函数中调用init_devs函数初始化这些结构体，初始化过程包括设定其minor（次设备号）、name（设备名称）和fops（各设备操作对应的函数指针）三个字段，不同结构体的name字段不同（包含各虚拟Binder设备的编号），其它字段相同。fops字段设定为虚拟Binder设备驱动中的conbinder_fops结构体的地址。初始化完成之后conbinder_init函数继续调用register_devs，后者循环调用misc_register函数将之前初始化好的虚拟Binder设备注册到内核中。这样，内核启动完成之后会在/dev目录下创建以设备名称命名的虚拟Binder设备文件。通过在mount命令中使用bind选项可以将这些设备文件与虚拟机根文件系统中的/dev/binder文件绑定，从而将其分配给虚拟机。虚拟机中的应用程序访问Binder设备时，内核将执行虚拟Binder设备驱动程序中的函数。

**3.构建共享服务列表配置接口**

(1).在proc文件系统中创建文件：

本发明中的共享服务列表配置接口借助proc文件系统实现。我们在conbinder_init函数中添加代码，先调用proc_mkdir函数在/proc目录下创建一个目录，然后调用create_proc_entry在该目录中创建一个名为sharedservices的文件，接着创建两个函数conbinder_proc_ss_read和conbinder_proc_ss_write并将它们分别设定为sharedservices文件的读、写回调函数。

(2).定义共享服务列表的数据结构：

文件创建成功之后我们在内核中分配一块内存用于存储写入sharedservices文件的数据，然后创建一棵红黑树services_tree用于索引该文件中存储的共享服务名。

(3).实现共享服务列表的读写：

当用户将共享服务名写入sharedservices文件时，内核将调用conbinder_proc_ss_write函数。该函数首先接收到的数据存储到之前分配的内存块中，然后将数据中包含的服务名字插入services_tree中。当用户读取sharedservices文件时，内核将调用conbinder_proc_ss_read函数，该函数读取内存块中的数据并返回给上层。

(4).实现服务共享：

为了实现服务共享的功能，我们在虚拟Binder设备的驱动程序中设置了一个白名单。如果拦截到的某个请求中的服务名字属于这个白名单，那么该请求将不会被修改。这样，虚拟机中不需要运行白名单中的服务，虚拟机中的客户端进程向Service Manager请求白名单中的某个服务时，Service Manager返回的将是主机中运行的服务。因此，白名单中的服务只需在主机中运行，被主机以及所有虚拟机中的客户端进程所共享。本发明中这个白名单即设置为services_tree这棵红黑树。虚拟Binder设备的驱动程序在修改请求中的服务名字之前会在services_tree中查找该服务名字，如果未找到则继续修改，如果找到则放弃修改。