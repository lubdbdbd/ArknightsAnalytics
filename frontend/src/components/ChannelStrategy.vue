<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import DataTable from './DataTable.vue'
const report=ref(null),error=ref(''),busy=ref(false),channel=ref(''),category=ref(''),decision=ref(''),query=ref(''),page=ref(1),reviewPage=ref(1),selected=ref(null)
const money=v=>v==null?'—':'¥'+Number(v).toFixed(2)
const pct=v=>v==null?'—':(v*100).toFixed(1)+'%'
const categories=computed(()=>[...new Set(report.value?.matrix.map(r=>r.category)||[])])
const decisions=computed(()=>Object.keys(report.value?.summary.decision_counts||{}))
const filtered=computed(()=>(report.value?.matrix||[]).filter(r=>(!channel.value||r.channel===channel.value)&&(!category.value||r.category===category.value)&&(!decision.value||r.decision===decision.value)&&(!query.value||(r.sku_code+' '+r.operator).toLowerCase().includes(query.value.toLowerCase()))))
const pages=computed(()=>Math.max(1,Math.ceil(filtered.value.length/12)))
const rows=computed(()=>filtered.value.slice((page.value-1)*12,page.value*12))
const reviews=computed(()=>(report.value?.price_reviews||[]).filter(r=>(!channel.value||r.channel_a===channel.value||r.channel_b===channel.value)&&(!category.value||r.category===category.value)))
const reviewPages=computed(()=>Math.max(1,Math.ceil(reviews.value.length/10)))
watch([channel,category,decision,query],()=>{page.value=1;reviewPage.value=1;selected.value=null})
async function reload(){busy.value=true;error.value='';try{const response=await fetch('/api/channel-strategy');const data=await response.json();if(!response.ok)throw new Error(data.detail||'加载失败');report.value=data;selected.value=null;page.value=1;reviewPage.value=1}catch(e){error.value=e.message}finally{busy.value=false}}
onMounted(reload)
defineExpose({reload})
</script>

<template>
<section class="channels">
 <article class="panel">
  <div class="panel-heading"><h3>渠道策略 · 从商品属性到配置候选</h3><span class="badge amber">模拟观察 / 待验证规划</span></div>
  <p>比较各渠道的商品结构，结合品类、价格带、补货周期与成本约束，判断哪些商品值得进入渠道评审。</p>
  <p class="muted">同一 SKU 可以跨渠道销售。差异化可以体现在组合、权益、服务与上市节奏；价差须结合这些条件复核。</p>
  <div class="controls"><a class="button white" href="/api/channel-strategy?download=markdown">导出分析报告</a><a class="button white" href="/api/channel-strategy?download=json">导出完整矩阵 JSON</a></div>
 </article>
 <p v-if="busy">正在核对模拟订单与商品主档…</p><p v-if="error" class="error-note">{{error}}</p>
 <template v-if="report">
  <div class="stats">
   <article class="panel"><span>模拟商品主档</span><strong>{{report.summary.sku_count}}</strong><small>7类周边 · 210个SKU</small></article>
   <article class="panel"><span>SKU × 规划渠道</span><strong>{{report.summary.sku_channel_evaluations.toLocaleString()}}</strong><small>适配评估数，不是上架量</small></article>
   <article class="panel"><span>待验证新渠道</span><strong>{{report.summary.prospective_channels}}</strong><small>众筹 / 零售代理 · 未接入订单</small></article>
   <article class="panel"><span>假设价差待复核</span><strong>{{report.summary.price_review_pairs}}</strong><small>同SKU渠道对，不是已发生冲突</small></article>
  </div>
  <article class="panel table-panel">
   <div class="panel-heading"><h3>7类渠道的模拟经营观察</h3><span class="badge gray">{{report.observed.period_start}} — {{report.observed.period_end}}</span></div>
   <p class="inset muted">{{report.observed.source_orders.toLocaleString()}}张模拟订单中有{{report.observed.paid_orders.toLocaleString()}}张支付订单，商品GMV {{money(report.observed.paid_merchandise_gmv)}}，已与订单头独立汇总核对。二手平台与其他仅作观察，不纳入可控渠道配置。</p>
   <DataTable :rows="report.observed.summary" :columns="[{key:'channel',label:'观察渠道'},{key:'paid_orders',label:'支付订单',type:'number'},{key:'merchandise_gmv',label:'商品GMV',type:'money'},{key:'paid_aov',label:'商品客单价',type:'money'},{key:'observed_sku_count',label:'有支付记录SKU',type:'number'}]"/>
  </article>
  <article class="panel">
   <div class="panel-heading"><h3>渠道定位与准入条件</h3><span class="badge gray">5类模拟渠道 + 2类规划渠道</span></div>
   <p class="notice">{{report.policy.assumption_notice}}</p>
   <div class="profile-grid">
    <details v-for="p in report.profiles" :key="p.id"><summary>{{p.channel}} <small>{{p.status}}</small></summary><p>{{p.positioning}}</p><p>配置建议：{{p.offer_plan}}</p><p>目录价格带：{{money(p.price_min)}}—{{money(p.price_max)}}；优先评审{{p.priority_count}}个，条件配置{{p.conditional_count}}个，成本待复核{{p.cost_review_count}}个。</p><p>假设折扣{{pct(p.discount_rate)}} / 渠道费{{pct(p.channel_fee_rate)}} / 退款{{pct(p.refund_rate)}} / 单位变动费用{{money(p.variable_cost_per_unit)}}。{{p.price_basis==='wholesale'?'价格口径为批发出货价。':'价格口径为商品零售价。'}}</p><ul><li v-for="text in p.requirements" :key="text">{{text}}</li></ul></details>
   </div>
  </article>
  <article class="panel">
   <h3>SKU配置筛选</h3>
   <p class="muted">品类 {{pct(report.policy.weights.category)}}、价格带 {{pct(report.policy.weights.price)}}、补货周期 {{pct(report.policy.weights.replenishment)}}、生产风险代理 {{pct(report.policy.weights.production)}}。先检查单件贡献率是否达到{{pct(report.policy.minimum_unit_margin)}}，再依据{{report.policy.priority_score}} / {{report.policy.conditional_score}}分划分评审优先级。规则可在配置文件中调整。</p>
   <div class="filters"><label>规划渠道<select v-model="channel" aria-label="规划渠道"><option value="">全部渠道</option><option v-for="p in report.profiles" :key="p.id">{{p.channel}}</option></select></label><label>周边品类<select v-model="category" aria-label="周边品类"><option value="">全部品类</option><option v-for="c in categories" :key="c">{{c}}</option></select></label><label>配置结论<select v-model="decision" aria-label="配置结论"><option value="">全部结论</option><option v-for="d in decisions" :key="d">{{d}}</option></select></label><label>角色 / SKU<input v-model="query" aria-label="搜索角色或SKU" placeholder="输入角色或编码"/></label></div>
  </article>
  <article class="panel table-panel"><div class="panel-heading"><h3>适配矩阵 · {{filtered.length}}条</h3><span class="muted">点击查看评分、成本与依据</span></div>
   <DataTable :rows="rows" action="查看依据" @select="selected=$event" :columns="[{key:'operator',label:'角色'},{key:'category',label:'品类'},{key:'channel',label:'规划渠道'},{key:'fit_score',label:'适配分',type:'number'},{key:'decision',label:'结论'},{key:'proposed_price',label:'假设渠道价',type:'money'},{key:'unit_margin',label:'假设贡献率',type:'percent'}]"/>
   <div class="pager"><button class="button white" :disabled="page<=1" @click="page--">上一页</button><span>{{page}} / {{pages}}</span><button class="button white" :disabled="page>=pages" @click="page++">下一页</button></div>
  </article>
  <article v-if="selected" class="panel detail"><div class="panel-heading"><h3>{{selected.operator}} · {{selected.category}} → {{selected.channel}}</h3><button class="button white" @click="selected=null">收起依据</button></div><p>{{selected.sku_code}} ｜ {{selected.decision}} ｜ {{selected.channel_status}}</p><p><b>配置建议：</b>{{selected.offer_plan}}</p><p><b>评分依据：</b>{{selected.reason}}</p><p>品类 {{selected.category_score}} / 价格 {{selected.price_score}} / 补货 {{selected.replenishment_score}} / 生产风险 {{selected.production_score}}。综合 {{selected.fit_score}}分。</p><p><b>模拟观察：</b>{{selected.observation_scope}}；支付订单 {{selected.observed_paid_orders??'未接入'}}；商品GMV {{money(selected.observed_gmv)}}；平均成交单价 {{money(selected.observed_price)}}。</p><p><b>独立规划假设：</b>{{selected.price_basis_label}} {{money(selected.proposed_price)}}；商品成本 {{money(selected.unit_cost)}}；单件贡献 {{money(selected.unit_contribution)}}（{{pct(selected.unit_margin)}}）。</p><p class="notice">{{selected.cost_scope}}</p><p><b>执行前确认：</b>{{selected.requirements}}</p></article>
  <article class="panel table-panel"><div class="panel-heading"><h3>品类 × 渠道配置概览</h3><span class="badge gray">49个组合，按渠道与品类筛选</span></div><DataTable :rows="report.category_matrix.filter(r=>(!channel||r.channel===channel)&&(!category||r.category===category))" :columns="[{key:'channel',label:'渠道'},{key:'category',label:'品类'},{key:'average_fit_score',label:'平均适配分',type:'number'},{key:'dominant_decision',label:'主要结论'},{key:'priority_count',label:'优先评审SKU',type:'number'},{key:'cost_review_count',label:'成本复核SKU',type:'number'}]"/></article>
  <article class="panel table-panel"><div class="panel-heading"><h3>跨渠道假设价差 · {{reviews.length}}组</h3><span class="badge amber">需核对权益、时间及履约条件</span></div><p class="muted inset">仅比较同SKU、同零售价口径且进入优先评审或条件配置的方案；价差阈值{{pct(report.policy.price_gap_review_threshold)}}（差额 / 较高价）。代理批发价不与零售价直接比较。本表随渠道和品类筛选。</p><DataTable :rows="reviews.slice((reviewPage-1)*10,reviewPage*10)" :columns="[{key:'operator',label:'角色'},{key:'category',label:'品类'},{key:'channel_a',label:'渠道A'},{key:'channel_b',label:'渠道B'},{key:'price_a',label:'假设价A',type:'money'},{key:'price_b',label:'假设价B',type:'money'},{key:'relative_gap',label:'价差比例',type:'percent'}]"/><div class="pager"><button class="button white" :disabled="reviewPage<=1" @click="reviewPage--">前10组</button><span>{{reviewPage}} / {{reviewPages}}</span><button class="button white" :disabled="reviewPage>=reviewPages" @click="reviewPage++">后10组</button></div></article>
  <article class="panel"><h3>从配置建议到渠道试点</h3><p>确认授权与准入 → 选择小批量候选 → 核实成本、库存和权益 → 明确活动周期与价格 → 记录成交、退款及履约 → 按同口径复盘。当前输出用于规划评审，尚未执行真实铺货或分销。</p><ul><li v-for="text in report.limitations" :key="text">{{text}}</li></ul><details><summary>输入文件与版本依据</summary><p v-for="f in report.manifest" :key="f.file" class="hash">{{f.file}}<br/>SHA256 {{f.sha256}}</p></details></article>
 </template>
</section>
</template>
<style scoped>
.channels{display:grid;gap:22px}.channels p,.channels li{font-size:13px;line-height:1.85}.channels ul{padding-left:22px}.channels .panel-heading{flex-wrap:wrap;gap:10px}.controls,.pager{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}.stats article{display:grid;gap:12px}.stats strong{font-size:27px;color:#36543a}.stats span,.stats small{font-size:12px;color:#637168}.inset{padding:0 24px}.notice{padding:12px 16px;background:#fff6e6;border-left:3px solid #be903c;color:#725621}.profile-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.profile-grid details{border:1px solid #e2e8df;padding:14px;border-radius:8px}.channels summary{cursor:pointer;line-height:1.7;font-size:14px}.channels summary small{margin-left:8px;color:#6d776d}.filters{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.filters label{display:grid;gap:8px;font-size:12px}.filters select,.filters input{width:100%;box-sizing:border-box;border:1px solid #dfe7df;padding:10px;background:white;border-radius:6px}.pager{padding:20px 24px;justify-content:flex-end;font-size:12px}.detail{border-top:3px solid #799678}.hash{overflow-wrap:anywhere}.error-note{color:#a23932}@media(max-width:1100px){.stats,.filters{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:650px){.profile-grid,.filters{grid-template-columns:1fr}}
</style>
