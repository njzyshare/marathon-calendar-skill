# 截图生成方法

## 前置条件
- 运行环境需要 Node.js 和 Playwright 包
- 在工作目录下操作（由上下文确定，通过 `${cwd}` 占位符获取）

## 生成步骤

1. 先生成 HTML 报告文件到工作目录
2. 用 Node.js 调用 Playwright 截取全页面长图：

```javascript
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  // 手机预览用 430px，桌面截图用 600px
  const page = await browser.newPage({ viewport: { width: 430, height: 900 } });
  await page.goto('file:///${cwd}/文件名.html', { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: '${cwd}/文件名.png', fullPage: true });
  await browser.close();
})();
```

## 关键参数
| 参数 | 值 | 说明 |
|------|-----|------|
| viewport width | 430px | 手机尺寸，截图分享友好 |
| fullPage | true | 截取全页面长图 |
| waitUntil | 'networkidle' | 等待资源加载完毕 |
| 截图前等待 | 1s | 让字体渲染完成 |

## 验证
- 检查生成的 PNG 文件大小 > 50KB
- 用 `present_files` 展示 HTML 和 PNG

## 注意
- 文件路径用 `${cwd}` 占位符，运行时由上下文替换
- 不要在 skill 文件中写死绝对路径
