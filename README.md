# myscript
自用脚本，用于自建NAS

cross_fill: 让多个下载不完全的种子相互分享文件块，仅限单文件种子，不稳定

ddns: 获取本机公网ipv4和ipv6，然后调用cloudflare api设置域名解析。

slaac_daemon: 手动处理基于slaac的ipv6地址分配，可以在获取前缀之后自定义主机号。这样得到的ipv6可以比较短。

update\_tracker: 根据延迟和稳定性为qbittorrent选择最好的tracker

m4a.sh: 将flac编码和mp3编码转换为苹果的m4a容器+alac/aac编码，方便导入苹果的音乐APP。