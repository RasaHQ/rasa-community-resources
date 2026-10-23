import fs from 'node:fs';import {createRequire} from 'node:module';const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');
const root=new URL('../',import.meta.url).pathname;
const browser=await chromium.launch({...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
const count=JSON.parse(fs.readFileSync(new URL('./slides.json',import.meta.url))).length;
let report={slides:count,viewports:[],failures:[]};
for(const [width,height] of [[1600,900],[1280,720]]){
 const page=await browser.newPage({viewport:{width,height}});let network=[];page.on('request',r=>{if(r.url().startsWith('http'))network.push(r.url())});page.on('pageerror',e=>report.failures.push(String(e)));
 await page.goto('file://'+root+'slides/index.html');await page.evaluate(()=>document.fonts.ready);
 for(let i=0;i<count;i++){
  await page.evaluate(i=>show(i),i);
  const bad=await page.evaluate(()=>{const s=document.querySelector('.slide.on'),r=s.getBoundingClientRect(),f=s.querySelector('footer').getBoundingClientRect();let failures=[];for(const el of s.querySelectorAll('h1,h2,p,li,pre,td,th,label,blockquote,.big-question,.quote,.hero-result')){const b=el.getBoundingClientRect();if(!b.width||!b.height)continue;if(b.left<r.left+2||b.right>r.right-2||b.bottom>f.top-4)failures.push({text:el.textContent.slice(0,60),reason:'outside safe bounds'});if(el.scrollWidth>el.clientWidth+3 && getComputedStyle(el).display!=='inline')failures.push({text:el.textContent.slice(0,60),reason:'horizontal overflow'});}return failures;});
  report.failures.push(...bad.map(x=>({...x,slide:i+1,width})));
 }
 await page.evaluate(()=>show(0));await page.keyboard.press('ArrowRight');if(await page.locator('.slide.on').getAttribute('id')!=='s2')report.failures.push('navigation');await page.keyboard.press('n');if(!await page.locator('body').evaluate(b=>b.classList.contains('notes')))report.failures.push('notes');
 report.viewports.push({width,height,networkRequests:network.length});
 await page.close();
}
const pdfPage=await browser.newPage({viewport:{width:1600,height:900}});await pdfPage.goto('file://'+root+'slides/index.html');await pdfPage.evaluate(()=>document.fonts.ready);await pdfPage.pdf({path:root+'slides/masterclass-slides.pdf',preferCSSPageSize:true,printBackground:true});
fs.writeFileSync(root+'verification/deck-qa.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));await browser.close();
