# Linux VM 合成恢复实证

2026-11-05，ARC-UPGRADE@0.1.0 / WP-05环境恢复前置研究，基线cad3703。只支持固定Linux引擎的辅助机制；不新增AC-17业务迁移通过，不证明Mac Desktop配置传递、原盘零写入或完整AC-19。完整last_verified=null，最终接受pending。

用户批准单VM逻辑≤6GiB/实际增长≤3GiB、同目标累计600分钟；另批准宿主OpenPGP.js6.3.2及5MiB精确网络限额修正。累计保留，无默认替换、后端分发或历史清理扩权。

## 实际结果

Lima2.2.1/VZ/plain、Debian12 ARM64、内核6.1.0-53-cloud-arm64，Docker28.3.2/e77ff99、containerd1.7.27、runc1.2.5。三DEB只在新guest用dpkg-deb -x，无maintainer scripts/apt或服务安装；六ELF绑定已签DEB成员，动态库无缺失。无宿主共享或Docker socket转发；容器network=none/无mount/--pull=never。

- 相同Exit137/manual/初始状态的五策略：restart=true启动4/5，仅手动停止的unless-stopped保持停；restart=false为0/5，StartedAt/RestartCount保持，3秒复查一致。
- sleep未响应TERM，停机最终137退出；on-failure因此按Moby28.3.2固定恢复逻辑启动。[ShouldRestart](https://github.com/moby/moby/blob/v28.3.2/container/container.go#L497-L501)与[策略分支](https://github.com/moby/moby/blob/v28.3.2/restartmanager/restartmanager.go#L75-L85)支持此限定，不能泛化版本/退出条件。
- live-restore两任务跨daemon关闭存活，restart=false后同PID/StartedAt/计数重连；此开关不停止存活任务。自建AutoRemove对象stop后消失，另一任务仍在。
- marker读回一致，但入口会重写同值，不能据此证明业务持久化或文件未写入。

最终c1d2 exit0/59.161秒。a1b2缺/bin/test、b1c2错误on-failure预期两次失败保留；每次先停新VM，再用新目录修正。最终无owned engine进程，stop probe exit0、回读Stopped。VM磁盘/下载/失败目录及现存data-root保留；AutoRemove消除自身新对象是实测行为，未手工清理历史。

## 来源与局限

inputs/signatures记录六主制品437,586,414B及验签。signatures的VM_created=false为创建前快照。Lima签名→包内Debian摘要属Lima发布者背书，非Debian签名；Docker签名索引→三包，Alpine直接签名；四项负控均拒绝。吊销仅覆盖取得的key material。

方法：专用LIMA_HOME仅probe由guard创建/启动；该VM SSH传入只读prerequisite，按本次boot/machine及唯一run-id调用冻结guest脚本；已核Alpine只在guest导入。guest/profile/guard源码按manifest选入；host验签与安装脚本仅保存方法/指纹，不冒称全部工具源码封存，也不授权自动重放。

result/observations是实际JSON选定字段，带完整源size/SHA；83,239B完整result和未选原件仅存临时runtime/VM。Packages.gz、key、归档、磁盘及完整日志不入Git。tmp可能被清理；Git仅能恢复manifest内小文件，不能恢复VM或数据库。

capacity记录epoch3正常结束及峰值；1秒观察不是硬配额，未触发停止。QCOW2初估压缩位解析偏低，创建后/首次boot前已修正，实际未触限。旧12GiB归属/增长warning仍open。

protection核10固定输入/11旧manifest一致，未重读全部历史payload。原Desktop12:59启动及Docker.raw元数据变化经只读发现，用户确认自己/另一任务启动；本代理未连接/启停/修改原引擎，不声称全局原盘/全部历史字节不变。

Sol实现、Astra独立只读复核、root实际执行集成；沿用spec-development，无UI变更。Mac准入/验收、系统/许可、AC-19和AD-03仍待解决。本轮未运行Langflow/API/PG全栈。
