# 截图生成方法

## 前置条件
- 运行环境需要 Node.js 和 Playwright 包
- 在工作目录下操作（由上下文确定）

## 生成步骤

1. 先生成 HTML 报告文件到工作目录
2. 用 Node.js 调用 Playwright 截取全页面长图：

```javascript
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 600, height: 800 } });
  await page.goto('file:///工作目录/文件名.html', { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: '工作目录/文件名.png', fullPage: true });
  await browser.close();
})();
```

## 关键参数
| 参数 | 值 | 说明 |
|------|-----|------|
| viewport width | 600px | 移动端/截图优化 |
| fullPage | true | 截取全页面长图 |
| waitUntil | 'networkidle' | 等待资源加载完毕 |
| 截图前等待 | 1s | 让字体渲染完成 |

## 验证
- 检查生成的 PNG 文件大小 > 50KB
- 用 `present_files` 展示 HTML 和 PNG

## 注意
- 文件路径需要用绝对路径（Playwright file:// 协议要求）
- 路径从工作目录推导，不在SKILL.md中写死
