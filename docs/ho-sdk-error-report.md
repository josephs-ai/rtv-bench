# Happy Oyster (Reactor SDK) 故障详情报告

日期:2026-08-13 · 项目:实时视频产品横评 · 账号:Reactor(公司 key,[redacted])

## 一句话结论

**Reactor 平台侧的 `attach_world` 指令自 8 月 12 日起失效(服务器端回归)**:世界在服务器上正常生成完毕(有世界 ID、有首帧 CDN 截图为证),但视频流永远不切换到世界内容,一直停留在纯色占位画面。我们的 SDK 调用方式没有变化,此前(8 月 10–11 日)同样代码工作正常。**这不是我们的集成错误,也不是欠费问题。**

## 时间线

| 时间 (CST) | 事件 |
|---|---|
| 8月10–11日 | HO director 模式经 Reactor SDK 采集正常(create_world → ready → attach_world → 真实世界画面) |
| 8月12日 白天 | 首次发现:attach 后画面停留纯色场;当日 3 次独立在线复测,全部复现 |
| 8月12日 17:46 | 绕过方案上线(浏览器抓帧,见下),D1–D5、W1 采集成功(2688–4320 帧真实内容) |
| 8月13日 01:57 | 夜间自动采集再次确认 SDK 路径仍坏:G1-r1 等待 365 秒,0 帧通过内容闸门 |
| 8月13日 ~01:45 起 | Reactor 402 credits_depleted,全部会话被拒(独立问题) |

## 技术证据(均有存档)

1. **世界生成本身成功**(`ho-attach-proof.json`,完整消息日志):
   - `world_state` 依次推进 `creating → building(generating) → ready`,约 55–80 秒;
   - ready 载荷携带 `encrypted_world_id=dHpmaEU0lINZtc81EZgHEr6q_8ZMxUX8rgtjL4WoCOc`、
     首帧 CDN 截图 URL(cdn3.aorizon.cn,可打开,内容正确)、
     `api_base_url=https://ws-gp1v1hyjh3vn9ar2.ap-southeast-1.maas.aliyuncs.com/api/v2/apps/happyoyster-1.0`。
   - **即:服务器上世界已经建好,内容存在。**
2. **attach_world 无任何效果**:发送后无错误、无回执(fire-and-forget),视频轨内容不变。
   同一会话连续采样 434 帧原始画面,逐帧像素标准差全部为 **0.0**(纯色,无任何内容)。
3. **director 与 adventure 两个模型同样失效**(`reactor/happy-oyster-director`、`-adventure` 均复现)。
4. **失败会话的服务器版本号:`0.0.0@1.20260811.21506`**。测评期间观察到 Reactor 服务端
   多次热更(20260805 → 20260810 → 20260811.21506),故障时间与服务端发版时间吻合,
   与我们的客户端无关(客户端代码未变)。
5. **夜间损失**:8 月 12–13 日夜,7 个 G 系列采集会话各等待 286–365 秒计费时长,全部 0 帧
   (`happy-oyster-G*-r1.json`,`went_live=false`)。这些是付费会话时间,产出为零。

## 我们已做的排除

- 同一 SDK、同一网络、同一晚上:LingBot-World 2 采集 19/21 成功 → 通道与集成无问题;
- create_world / world_state 监听 / attach 时序均按平台行为实现(ready 后才 attach);
- 未知指令平台不回错误,已通过消息全量日志确认不是我们发错指令名;
- **不是欠费/计费问题**:该账号真正欠费时的表现是会话直接被拒(`402 credits_depleted`,
  会话根本建不起来,当晚稍后已亲历,特征完全不同)。而 attach 故障中会话正常建立、
  世界完整生成(这是计费大头)、首帧已渲染并上传 CDN、WebRTC 轨道正常送出 434 帧——
  只是内容永远不切换;且同账号同晚 LingBot 正常出流,排除账号级计费拦截。

## 临时绕过(已在用)

浏览器抓帧通道:用 Chrome DevTools Protocol 对 reactor.inc 网页版世界画布截屏采集
(D1–D5、W1 即此来源,原生 retina 分辨率)。**在报告中单独标注为 browser-capture lens,
不与 SDK lens 混table。** 该通道证明:网页版能看到世界 → 问题特定于 SDK/WebRTC 轨道路由。

## 对 Reactor 的诉求(建议原文转发)

1. 修复 `attach_world` 后 WebRTC 轨道不切换世界内容的问题(附上方 world_id 与时间戳可查);
2. 对 8 月 12–13 日产出为零的付费会话时长予以退还/补偿(约 7 会话 × 5–6 分钟,另有 3 次复测);
3. 告知修复时间表;修复前我们暂停 HO 的 SDK 采集(避免继续烧钱)。
