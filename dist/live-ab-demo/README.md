# 实时视频 AI 现场对比 Demo(Lucy 2.5 vs Xmax X2.0)

打开摄像头,把**同一路画面**同时喂给两款实时视频生成产品,左右并排实时显示。
哪边是哪家默认隐藏(加载时随机分边),看够了点 **Reveal sides** 揭晓 ——
先形成判断,再看厂商。

> 这是演示玩具,不是测量工具:页面不录制、不打时间戳、不产生任何评测数据。
> 正式评测走独立的标定管线(双镜头、盲评、锚定评分)。

## 运行条件

- macOS + Google Chrome(页面会自动弹出)
- Python 3(系统自带即可,无第三方依赖)
- 两个密钥,填入本目录 `.env`(参考 `.env.example`):
  - `DECART_API_KEY` — Lucy 2.5(Decart)
  - `XMAX_API_KEY` — Xmax 永久密钥(uk- 开头;程序会自动铸造限额临时密钥,
    单次上限 500 点,忘关窗口也烧不穿)
- 网络(在国内跑的关键):
  - Lucy 走海外,需要 VPN 且**出口放行 UDP**(很多 VPN 出口只转发 TCP,
    表现为"连上了但画面全黑");
  - Xmax 走国内直连,需要 VPN 分流排除 `*.xmaxai.com`,并建议开启
    "不修改 DNS"类选项(VPN 的 DNS 会把 xmaxai.com 解析到境外死 IP)。
  - 先跑 `python3 net_verify.py`,它会用大白话告诉你当前网络下哪边能通。

## 用法

```bash
cd live-ab-demo
cp .env.example .env   # 填入两个密钥
python3 net_verify.py  # 可选:网络体检
python3 live_ab.py     # 启动,Chrome 自动打开
```

- 顶部输入任意风格提示词,回车即同时应用到两边(Lucy 实时切换,
  Xmax 走官方 change-condition 接口);
- 预置词条分两类:整体重绘(油画/动漫/赛博朋克…)与**增添型**
  (肩上的龙、身边的动漫角色、身后的烟花…)—— 后者更能看出空间控制力;
- **Hide watermarks**:放大裁边,把厂商水印推出画面(两边同等处理);
- 关掉窗口即结束会话(开着期间两边都在计费:Lucy 按秒,Xmax 扣点)。

## 已知现象(不是 bug)

- 首帧要等几秒(Lucy 约 2–5 秒,Xmax 稍长);
- 画面轻微脉冲感:两家产品本身就是分块突发式出帧(实测特性);
- 偶发 1–2 秒卡顿:VPN 隧道丢包所致,与产品无关;
- 提示词被拒(prompt REJECTED):厂商内容审核在起作用,换温和措辞即可
  (僵尸/乐高化真人等都撞过线)—— 两家审核口径不同,本身就是产品差异。

## 文件说明

| 文件 | 作用 |
|---|---|
| `live_ab.py` | 启动器:本地起服务、铸 Xmax 临时密钥、注入密钥、拉起 Chrome |
| `web/live_ab.html` | 页面本体:摄像头采集、双路连接、盲评分边、提示词控制 |
| `web/vendor/` | Xmax 官方浏览器 SDK(vendored)及其依赖桩 |
| `net_verify.py` | 网络体检:UDP/各产品可达性,一句话结论 |
| `.env.example` | 密钥模板(真实密钥不要提交/转发) |
