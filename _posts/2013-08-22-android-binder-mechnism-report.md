---
layout: post
title: "Android Binder Mechnism Report"
description: ""
category: 
tags: []
---
{% include JB/setup %}
###Binder简介
Binder是Android系统新增的进程间通信机制，尽管Linux内核中已经拥有众多的进程间通信机制，Android却还要引入一整套新的机制，说明Binder具有无可比拟的优势。
###Binder优势
1. 基于C-S通信方式，适合智能设备平台的应用模式，如系统可以为APP开发者提供一些预装的服务如：媒体播放，音视频捕获，各种传感器等;
1. 传输性能: 与socket比，其传输效率高，开销小，适合本机的进程间高速通信;与消息队列和管道比，其数据拷贝次数少;
1. 安全性： 移动设备的安全性要求高，传统的IPC没有任何安全措施，接收方无法获得发送方进程可靠的PID/UID，无法鉴别对方身份。  

基于以上，Android需要建立一套新的适合移动设备应用特点的IPC机制。Binder充分考虑了传输性能，安全性，基于C-S模式，传输过程只需一次内存数据拷贝。
###Binder中的四个角色
Binder通信过程中共有四个角色（进程）参与：Client，Sever，  ServiceMangaer，Driver。其中 Server，Client，SMgr运行于用户空间，驱动运行于内核空间。这四个角色的关系和互联网类似：Server是服务器，Client是客户终端，SMgr是域名服务器（DNS），驱动是路由器。  
四个角色的关系如下图所示：  
![](http://hi.csdn.net/attachment/201107/19/0_13110996490rZN.gif)  

1. Client、Server和Service Manager实现在用户空间中，Binder驱动程序实现在内核空间中

2. Binder驱动程序和Service Manager在Android平台中已经实现，开发者只需要在用户空间实现自己的Client和Server

3. Binder驱动程序提供设备文件/dev/binder与用户空间交互，Client、Server和Service Manager通过open和ioctl文件操作函数与Binder驱动程序进行通信

4. Client和Server之间的进程间通信通过Binder驱动程序间接实现,即每次通信的数据包需要经由Driver处理后转发

5. Service Manager是一个守护进程，用来管理Server，并向Client提供查询Server接口的能力  

**Binder Driver**  
它工作于内核态，提供open(), mmap(), poll(), ioctl()等标准文件操作的；以字符设备中的misc设备类型注册，用户通过/dev/binder可以与其交互; 其负责Binder通信的建立/Binder在进程间的传递/Binder引用计数管理/数据包的传输等。  

**ServiceMgr**  
ServiceMgr的作用是将字符形式的Binder名字转化为一个该Binder的引用。Server创建了一个Binder实体，为其起一个名字，将这个名字封装成数据包，传输给Driver，Driver发现这个是新的Binder是来注册的，于是在内核中创建该Binder的实体节点（Binder_node）和一个对该实体的引用（Binder_ref），然后Driver将这个引用传递给ServiceMgr，ServiceMgr接收到数据包后，从中取出该Binder的名字和引用，填入一张查找表中。  

**Client**  
Client一开始只知道自己要使用的Binder的名字，和ServiceMgr中Binder实体的0号引用。首先通过0号引用去访问SMgr，获得想要使用的Binder的引用（只知道名字没用，需要获得引用）。SMgr查到引用后，回复给Client。获得引用后，Client就可以在本地像使用本地对象的成员函数一样调用Bidner实体的函数。

**匿名Binder**  
并不是所有Binder都需要到SMgr中注册的。许多情况下Server会将某Binder实体放在数据包中传输给Client，Server会在数据包中表明Binder实体的位置，驱动会为该匿名Binder建立node和ref，并将ref传递给Client。


###Binder协议
进程通过ioctl（fd,cmd,arg）函数实现交互。fd指向/dev/binder，cmd为命令，arg为数据。下表列举了所有的命令和对应的数据：  

<table>
   <tr>
      <td><strong>命令</td>
      <td><strong>args</td>
      <td><strong>含义</td>
   </tr>

   <tr>
      <td>BINDER_WRITE_READ</td>
      <td>struct binder_write_read{}</td>
      <td>向Binder中写入和读取数据</td>

   </tr>

   <tr>
      <td>BINDER_SET_MAX_THREADS</td>
      <td>int max_threads</td>
      <td>Server告之驱动其线程池中的线程数的最大值</td>
   </tr>

<tr>
      <td>BINDER_SET_CONTEXT_MGR</td>
      <td>无</td>
      <td>当前进程申请注册为SMgr，驱动为其创建无名node和0号ref</td>
   </tr>

<tr>
      <td>BINDER_THREAD_EXIT</td>
      <td>无</td>
      <td>告之驱动当前线程退出了，线程在退出时请求驱动释放为其建立的内核数据结构</td>
   </tr>

<tr>
      <td>BINDER_VERSION</td>
      <td>无</td>
      <td>获得Binder驱动的版本号</td>
   </tr>
</table>

**写Binder**  
Binder写操作的数据格式同样也是（命令+数据）。这时候命令和数据都存放在binder_write_read 结构write_buffer域指向的内存空间里，多条命令可以连续存放。数据紧接着存放在命令后面，格式根据命令不同而不同。下表列举了Binder写 操作支持的命令：

<table>
<tr>
<td><strong>命令</td>
<td><strong>arg</td>
<td><strong>含义</td>
</tr>

<tr>
<td>BC_TRANSACTION</td>
<td>struct binder_transaction_data</td>
<td>用于写入请求数据，数据存放在transaction_data中</td>
</tr>
<tr>
<td>BC_REPLY</td>
<td>struct binder_transaction_data</td>
<td>用于写入回复数据，数据存放在transaction_data中</td>
</tr>
</table>

**读Binder**  
读Binder的数据格式采用消息+数据形式，跟写Binder基本一样。多条消息可以连续存放。下表列举了Binder读操作支持的消息：

<table>
<tr>
<td><strong>命令</td>
<td><strong>arg</td>
<td><strong>含义</td>
</tr>

<tr>
<td>BR_TRANSACTION</td>
<td>struct binder_transaction_data</td>
<td>表明当前数据包是发送方的请求数据</td>
</tr>
<tr>
<td>BR_REPLY</td>
<td>struct binder_transaction_data</td>
<td>表明当前数据包是发送方的回复数据</td>
</tr>
</table>

**struct binder_transaction_data**  
binder_transaction_data是Binder收发的数据包，了解它具有重要意义。

	struct binder_transaction_data {
	union {
		size_t	handle;	
		void	*ptr;	
	} target; 
	void		*cookie;
	unsigned int	code;
	unsigned int	flags;
	pid_t		sender_pid;
	uid_t		sender_euid;
	size_t		data_size;
	size_t		offsets_size;

	union {
		struct {
			const void __user	*buffer;
			const void __user	*offsets;
		} ptr;
		uint8_t	buf[8];
	} data;
	};


- 对于第一个联合体，指明了发送的目的地。 由于目的在远端，所以这里填入的是Binder实体的引用，存放在target.handle中; 当数据包经由驱动时，驱动将该成员修改成Binder实体，即Binder对象的指针，填入target.ptr; 数据包返回时，该过程逆过来。  
- cookie，在接收方受到数据包时，该成员存放的是创建Binder实体时由该接收方自定义的任意数值，作为Binder指针的备注信息。发送方和驱动都忽略该成员。  
- code，该成员存放收发双方约定的命令码，通常是Server端定义的公共函数的编号。  
- flags, 与交互相关的标志位。如TF_ONE_WAY表明这次交互是异步的，接收方不会返回任何数据，驱动利用该位来决定是否构建与返回有关的数据结构。  
- pid/uid，该成员存放发送方的进程ID和用户ID，由驱动负责填入，接收方可以读取该成员获知发送方的身份，提高了安全性。  
- data_size, 指明了真正存放实际数据的缓冲区的大小。  
- offsets_size, 驱动一般不会关心data.buffer里的数据，不会处理它。但是如果其中包含了Binder实体的传输，则需要让驱动知道。有可能存在多个Binder同时在数据包中，本成员表示有少个binder。  
- 该联合体中data.buffer指向真正存放数据的缓冲区;data.offset指向了数据包中匿名Binder实体相对于数据包头的偏移。在数据包中传输的Binder是类型为struct flat_binder_object。


接收方在收到binder_transaction_data后，首先解析消息头，然后真正的数据存放在data.buffer中

###Binder的表述
在Android系统中，不同角色的进程中的Binder的功能是不同的，表现形式是不同的，对Binder的理解也是不同的。接下来深入探讨Binder在四个角色中的表现形式和对应的数据结构。  

**Binder在Server端的表述**  
首先系统已经存在两个基类：（1）抽象接口类封装Server所有的功能，是一系列虚函数。由于这些函数需要跨进程调用，须为其一一编号，从而Server可以根据收到的编号决定调用哪个函数;（2）Binder抽象类处理来自Client的数据包，其中最重要的成员函数是onTransact()。该函数解析收到的数据包，调用相应的接口函数来处理。  
接下来，Server会继承这两个基类，构建自己的Binder类，生成Binder对象实体。Server会实现基类里所有的虚函数。  

**Binder在Client端的表述**  
Clinet端的Binder也要继承抽象接口类。采用的是Proxy设计模式，即Clinet利用SMgr发来的远端Binder的引用，在本地重新封装一次远程函数调用。（对于代理模式，看了大话设计模式之代理模式之后就很容易理解了）  
由于继承了同样的server接口类，Client Binder类需要和Server Binder实现同样的虚函数，使用户感受不出来Client调用的成员方法是在本地还是在远端。  
Clinet Binder类中，公共接口函数的底层实现方式是：创建一个binder_transaction_data数据包，将其对应的编码填入code域，将参数填入data.buffer指向的缓冲区，并设定数据包的目的地（将获得的Binder实体的引用handle填入数据包的target.handle中）。  

**Binder在传输数据中的表述**  
前面说了，Binder是塞在数据包中传给接收方的，这些传输中的Binder是用struct flat_binder_object表示的：

	struct flat_binder_object {
	unsigned long		type;
	unsigned long		flags;

	union {
		void __user	*binder;
		signed long	handle;	
	};

	void __user		*cookie;
	};


**Binder在驱动中的表述**  
驱动是Binder通信的核心，系统中所有的Binder实体以及每个实体在各个进程中的引用都登记在驱动中；驱动需要记录Binder引用 ->实体之间多对一的关系；为引用找到对应的实体；为某个进程中的实体创建或查找到对应的引用；记录Binder的归属地（位于哪个进程中）；通过 管理Binder的强/弱引用创建/销毁Binder实体等等。  

驱动里的Binder是什么时候创建的呢？当每个server为自己的Binder实体向SMgr注册的时候，驱动都会感知到。而ServiceMgr作为系统第一个申请注册的Binder，那时候binder机制还未建立起来，所以内核就给它开了另外一条绿色通道，即创建无名内核binder实体，和创建0号binder实体引用。  
随着各种各样Server不断地注册实名binder，不断向SMgr索要Binder的引用，不断将Binder引用从一个进程传递给另一个进程，越来越多的Binder以flat_binder_object形式穿越驱动做进程间的迁徙，里面最重要的是binder实体的引用。  

Binder将对每个经过它的binder结构做如下处理：首先检查传输结构的type域，如果是BINDER_TYPE_BINDER或BINDER_TYPE_WEAK_BINDER则创建内核的binder实体;如果是BINDER_TYPE_HANDLE或BINDER_TYPE_WEAK_HANDLE则创建binder的引用。随着越来越多的Binder实体或引用穿过驱动在进 程间传递，驱动会在内核里创建越来越多的节点或引用，当然这个过程对用户来说是透明的。

**Binder实体在驱动中的表述**  
驱动中的Binder实体也叫节点，隶属于提供实体的进程，由struct binder_node结构来表示：

	struct binder_node {
	int debug_id;
	struct binder_work work;
	union {
		struct rb_node rb_node;
		struct hlist_node dead_node;
	};
	struct binder_proc *proc;
	struct hlist_head refs;
	int internal_strong_refs;
	int local_weak_refs;
	int local_strong_refs;
	void __user *ptr;
	void __user *cookie;
	unsigned has_strong_ref:1;
	unsigned pending_strong_ref:1;
	unsigned has_weak_ref:1;
	unsigned pending_weak_ref:1;
	unsigned has_async_transaction:1;
	unsigned accept_fds:1;
	unsigned min_priority:8;
	struct list_head async_todo;
	};
驱动在内核中为每个进程维护一棵红黑树来存放该进程创建的binder实体。以flat_binder_object中的binder域为索引。如果没有找到就创建一个新节点并添加到红黑树中。  

- proc，本成员指向节点所属的进程，即提供该Binder节点的进程。
- ptr，指向用户空间Binder实体的指针，来自于flat_binder_object的binder成员

**Binder引用在驱动中的表述**  
和实体一样，Binder的引用也是驱动根据传输数据中的flat_binder_object创建的，隶属于获得该引用的进程，用struct binder_ref表示：

	struct binder_ref {
	int debug_id;
	struct rb_node rb_node_desc;
	struct rb_node rb_node_node;
	struct hlist_node node_entry;
	struct binder_proc *proc;
	struct binder_node *node;
	uint32_t desc;
	int strong;
	int weak;
	struct binder_ref_death *death;
	};

驱动为每个进程维护一棵红黑树来存放该进程所有正在使用的引用。驱动可以通过两个键值来帮助进程索引Binder引用：  

- 对应binder节点在内核中的地址。即驱动中该binder对应的binder_node的地址。
- 引用号。引用号是驱动为引用分配的一个32位标识，在一个进程内是唯一的，而在不同的进程内可能会相同。引用号返回给用户程序，可以看作是Binder引用在用户程序中的句柄。除了0号引用号在所有进程里都保留给SMgr，其他值由驱动在创建引用时动态分配。向binder发送binder_transaction_data数据包时，应用程序将此引用号填入target.handle域中指明目的binder。驱动根据该引用号在发送方进程的红黑树中索引到binder_ref,进而通过其node域获得其对应的binder_node地址，再从binder_node的proc域找到binder实体所在的进程及其他信息。

###Binder内存映射
Binder采用一种全新策略：由Binder驱动负责管理数据接收缓存。即数据存放在驱动的缓冲区中，同时驱动将这片缓冲区再映射到接收进程的缓冲区中，这样只需将发送方的数据拷贝至内核缓冲区即可，接收方由于已经映射了这片缓冲区，所以也相当与拥有这片数据了。






