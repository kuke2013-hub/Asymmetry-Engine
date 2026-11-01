/* Browser-level adversarial checks against the REAL deployed release.
 * Synthetic records exist only inside Playwright intercepted responses;
 * they are never committed to the public product feed.
 */
const { chromium } = require('playwright-core');
const { execFileSync } = require('child_process');
const { readFileSync } = require('fs');
const assert = require('node:assert/strict');
const version=JSON.parse(readFileSync('config/site-release.json','utf8')).version;
const URL='https://kuke2013-hub.github.io/Asymmetry-Engine/versions/'+version+'/';
const binary=process.env.CHROME_PATH||'/usr/bin/google-chrome';
const base={
 schema_version:3,
 data_type:'retailer_product_listings_only',
 product_count:1,
 products:[{
  market:'JP', source:'rakuten_jp_item_search', product_id:'fixture-shop:box',
  title:'TEST FIXTURE (not published)', category:'storage_organisation', price:1600,
  currency:'JPY',product_url:'https://item.rakuten.co.jp/fixture-shop/box/',
  observed_at:new Date().toISOString()
 }],
 source_status:[{source:'rakuten_jp_item_search',market:'JP',category:'storage_organisation',
                status:'success',accepted:1,rejected:0}],
 generated_at:new Date().toISOString()
};
async function run(){
const browser=await chromium.launch({executablePath:binary,headless:true,
 args:['--no-sandbox','--disable-gpu','--ignore-certificate-errors']});
try {
const context=await browser.newContext({ignoreHTTPSErrors:true,viewport:{width:390,height:844}});
for(const [label,payload] of [
  ['stale', {...base,generated_at:'2020-01-01T00:00:00Z'}],
  ['malformed', {...base,data_type:'general_search_topics'}],
  ['news', {...base,products:[{...base.products[0],source:'google_trending_rss',
                                product_id:'andreas-almgren',title:'andreas almgren'}]}]
]){
const page=await context.newPage();
await page.route('**/reports/product-only.json',async route=>{
await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(payload)});
});
await page.goto(URL,{waitUntil:'networkidle',timeout:30000});
await page.waitForTimeout(250);
const status=await page.locator('#status-title').textContent();
const products=await page.locator('#products .product').count();
assert.equal(products,0,label+': untrusted product card shown');
if(label==='stale') {
 assert.match(status,/stale/i);
 assert.equal(await page.locator('#product-count').textContent(),'Not current');
}else if(label==='malformed'){
 assert.match(status,/unavailable/i);
}else{
 assert.equal(await page.locator('#product-count').textContent(),'0');
 assert.equal(await page.getByText('andreas almgren',{exact:true}).count(),0);
}
console.log('BROWSER SAFETY PASS',label,status);
await page.close();
}
await context.close();
} finally {await browser.close();}
}
run().catch(error=>{console.error(error);process.exitCode=1});
