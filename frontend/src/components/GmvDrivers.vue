<script setup>
import { ref, computed, onMounted } from 'vue'
import DataTable from './DataTable.vue'
const report=ref(null), error=ref(''), busy=ref(false), computing=ref(false), selected=ref('bundle')
const base=ref({}), candidate=ref({}), result=ref(null), submitted=ref('')
const fields=[
 {key:'visitors',label:'访客UV（人）',min:0,step:1},
 {key:'buyer_conversion',label:'购买用户转化率（%）',min:0,max:100,step:.1,percent:true},
 {key:'purchase_frequency',label:'人均支付订单数',min:1,step:.1},
 {key:'list_basket_value',label:'购物篮优惠前金额（元）',min:.01,step:.01},
 {key:'discount_rate',label:'优惠比例（%）',min:0,max:100,step:.1,percent:true},
 {key:'cogs_per_order',label:'每单商品成本（元）',min:0,step:.01},
 {key:'fulfillment_per_order',label:'每单履约成本（元）',min:0,step:.01},
 {key:'gift_per_order',label:'每单赠品成本（元）',min:0,step:.01},
 {key:'platform_fee_rate',label:'平台费率（%）',min:0,max:100,step:.1,percent:true},
 {key:'refund_amount_rate',label:'退款金额比例（%）',min:0,max:100,step:.1,percent:true},
 {key:'marketing_spend',label:'周期推广投入（元）',min:0,step:1},
 {key:'order_capacity',label:'承接订单上限（空为无限制）',min:0,step:1,optional:true}]
const observed=computed(()=>report.value?.observed)
const scenario=computed(()=>report.value?.strategies.find(r=>r.id===selected.value))
const dirty=computed(()=>submitted.value!==JSON.stringify([base.value,candidate.value]))
const money=v=>v===null||v===undefined?'—':'¥'+Number(v).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})
const pct=v=>v===null||v===undefined?'—':(v*100).toFixed(2)+'%'
function toForm(p){return Object.fromEntries(fields.map(f=>[f.key,p[f.key]===null?'':f.percent?Number((p[f.key]*100).toFixed(8)):p[f.key]]))}
function toPayload(p){return Object.fromEntries(fields.map(f=>[f.key,p[f.key]===''&&f.optional?null:f.percent?Number(p[f.key])/100:Number(p[f.key])]))}
function choose(){candidate.value=toForm(scenario.value.parameters);result.value=null}
async function calculate(){
 computing.value=true;error.value='';const snapshot=JSON.stringify([base.value,candidate.value])
 try{const response=await fetch('/api/gmv-drivers/scenario',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({base:toPayload(base.value),candidate:toPayload(candidate.value)})});const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'请检查输入范围与必填字段');result.value=data;submitted.value=snapshot}
 catch(e){error.value=e.message;result.value=null}finally{computing.value=false}
}
async function load(){busy.value=true;error.value='';try{const response=await fetch('/api/gmv-drivers');const data=await response.json();if(!response.ok)throw Error(data.detail||'读取失败');report.value=data;base.value=toForm(data.baseline.parameters);choose();await calculate()}catch(e){error.value=e.message}finally{busy.value=false}}
onMounted(load)
defineExpose({reload:load})
</script>

<template>
<section class="gmv">
 <article class="panel"><div class="panel-heading"><div><h3>先拆成交，再算每笔生意的贡献</h3><p>订单分析与营销假设分别展示。原始数据保留，情景测算不会修改商品售价或执行营销活动。</p></div><div class="controls"><a class="button white" href="/api/gmv-drivers?download=markdown">导出分析报告</a><a class="button white" href="/api/gmv-drivers?download=json">下载计算依据</a></div></div><p v-if="busy" role="status">正在核对订单与测算情景…</p><p v-if="error" role="alert" class="error-note">{{error}}</p></article>
 <template v-if="report">
  <div class="gmv-stats"><article class="panel"><span>模拟支付商品GMV</span><strong>{{money(observed.summary.paid_merchandise_gmv)}}</strong><small>不含运费，未扣退款</small></article><article class="panel"><span>模拟支付订单</span><strong>{{observed.summary.paid_orders.toLocaleString()}}</strong><small>已剔除 {{observed.summary.cancelled_orders}} 张取消订单</small></article><article class="panel"><span>模拟商品客单价</span><strong>{{money(observed.summary.paid_aov)}}</strong><small>优惠后商品金额 ÷ 支付订单数</small></article><article class="panel"><span>访问转化 / 复购</span><strong>待补数据</strong><small>缺少访客数据与客户唯一标识</small></article></div>
  <article class="panel"><h3>口径统一 · {{observed.period_start}} 至 {{observed.period_end}}</h3><p class="formula">支付商品GMV = 支付订单数 × 商品客单价</p><p class="muted">有用户级数据时，可进一步拆为：访客UV × 购买用户转化率 × 人均支付订单数 × 商品客单价。复购率不是可直接替代购买频次的乘数。</p><ul><li v-for="text in observed.metric_notes" :key="text">{{text}}</li></ul><p>订单支付完成率：{{pct(observed.summary.order_payment_completion_rate)}}；每单件数：{{observed.summary.units_per_order}}。均为模拟订单统计。</p><p class="warning-note">旧售后快照中 {{observed.refund_audit.orders_exceeding_cash}} 个订单退款超过含运费实付，{{observed.refund_audit.orders_exceeding_merchandise}} 个超过商品实付。当前暂不展示扣退款净销售或实测利润。</p></article>
  <article v-if="observed.comparison.status==='available'" class="panel"><h3>连续两个28日窗口 · GMV变化从哪里来</h3><p class="muted spaced">{{observed.comparison.before_start}}—{{observed.comparison.before_end}} 对比 {{observed.comparison.after_start}}—{{observed.comparison.after_end}}；模拟订单的会计式拆解，不是活动效果归因。</p><div class="contributions"><div><span>支付订单数变化贡献</span><strong>{{money(observed.comparison.order_count_contribution)}}</strong></div><div><span>客单价变化贡献</span><strong>{{money(observed.comparison.aov_contribution)}}</strong></div><div><span>GMV净变化</span><strong>{{money(observed.comparison.gmv_change)}}</strong></div></div><p class="muted">{{observed.comparison.method}} {{observed.comparison.reconciled?'金额核对通过。':'样本不足，无法分解。'}}</p></article>
  <article class="panel table-panel"><div class="panel-heading"><h3>按渠道诊断订单与客单价</h3><span class="badge">模拟数据 · {{observed.channels.length}}类渠道</span></div><DataTable :rows="observed.channels" :columns="[{key:'channel',label:'渠道'},{key:'paid_orders',label:'支付订单',type:'number'},{key:'paid_merchandise_gmv',label:'商品GMV',type:'money'},{key:'paid_aov',label:'商品客单价',type:'money'},{key:'units_per_order',label:'每单件数',type:'number'},{key:'discount_amount',label:'优惠金额',type:'money'},{key:'order_payment_completion_rate',label:'订单支付完成率',type:'percent'}]"/></article>
  <article class="panel table-panel"><div class="panel-heading"><h3>4类营销策略 · 固定假设对比</h3><span class="badge amber">未执行真实营销实验</span></div><p class="muted inset">{{report.assumption_notice}} 默认基准：{{report.baseline.parameters.visitors}}访客、{{pct(report.baseline.parameters.buyer_conversion)}}购买用户转化、每人{{report.baseline.parameters.purchase_frequency}}单；GMV {{money(report.baseline.paid_merchandise_gmv)}}、贡献利润 {{money(report.baseline.contribution_profit)}}。</p><DataTable :rows="report.strategies" :columns="[{key:'name',label:'情景'},{key:'expected_paid_orders',label:'预计支付订单',type:'number'},{key:'paid_merchandise_gmv',label:'假设GMV',type:'money'},{key:'contribution_profit',label:'假设贡献利润',type:'money'},{key:'gmv_change',label:'GMV较基准变化',type:'money'},{key:'contribution_change',label:'贡献较基准变化',type:'money'}]"/></article>
  <article class="panel"><div class="panel-heading"><h3>交互测算 · 修改假设，检查利润与承接约束</h3><select v-model="selected" @change="choose" aria-label="选择营销情景"><option v-for="r in report.strategies" :key="r.id" :value="r.id">{{r.name}}</option></select></div><p>预设方案说明：{{scenario?.hypothesis}} 修改后以输入参数为准。</p>
   <form @submit.prevent="calculate"><details><summary>调整对比基准（独立假设，不是ERP实测基准）</summary><div class="input-grid"><label v-for="field in fields" :key="field.key">基准 · {{field.label}}<input :aria-label="'基准 '+field.label" v-model.number="base[field.key]" type="number" :min="field.min" :max="field.max" :step="field.step" :required="!field.optional"/></label></div></details><div class="input-grid"><label v-for="field in fields" :key="field.key">{{field.label}}<input :aria-label="'方案 '+field.label" v-model.number="candidate[field.key]" type="number" :min="field.min" :max="field.max" :step="field.step" :required="!field.optional"/></label></div><div class="controls"><button class="button white" :disabled="computing" type="submit">{{computing?'计算中…':'计算当前方案'}}</button><span v-if="dirty" class="muted">参数已修改，请重新计算。</span></div></form>
   <template v-if="result&&!dirty"><div class="contributions spaced"><div><span>预计支付订单</span><strong>{{result.expected_paid_orders}}</strong></div><div><span>假设GMV</span><strong>{{money(result.paid_merchandise_gmv)}}</strong></div><div><span>假设贡献利润</span><strong>{{money(result.contribution_profit)}}</strong></div></div><p :class="result.gmv_up_profit_down?'warning-note':'muted'">GMV较基准 {{money(result.gmv_change)}}；贡献利润较基准 {{money(result.contribution_change)}}。{{result.gmv_up_profit_down?'当前出现成交额增加、贡献利润下降。':''}}</p><p>每单贡献：{{money(result.unit_contribution)}}；覆盖推广投入需 {{result.breakeven_orders??'无法计算'}} 单；达到基准贡献利润需 {{result.orders_to_match_base_contribution??'无法计算'}} 单。{{result.match_base_feasible?'在假设流量和容量上限内可达到，但需求仍需验证。':'当前约束下无法达到基准贡献利润。'}}</p><ul class="warning-note" v-if="result.alerts.length"><li v-for="text in result.alerts" :key="text">{{text}}</li></ul><p class="muted">{{result.boundary}}</p></template>
  </article>
  <article class="panel table-panel"><div class="panel-heading"><h3>12组敏感性情景 · 转化假设上下浮动20%</h3><span class="badge gray">固定预设，与上方手动测算分开</span></div><DataTable :rows="report.sensitivity" :columns="[{key:'strategy',label:'策略'},{key:'conversion_multiplier',label:'转化假设倍数',type:'number'},{key:'buyer_conversion',label:'购买用户转化率',type:'percent'},{key:'paid_merchandise_gmv',label:'假设GMV',type:'money'},{key:'contribution_profit',label:'假设贡献利润',type:'money'},{key:'contribution_change',label:'贡献较基准变化',type:'money'}]"/></article>
  <article class="panel"><h3>从测算到验证 · 待执行方案</h3><div v-for="r in report.strategies" :key="r.id"><h4>{{r.name}}</h4><p>{{r.experiment}}</p></div><h4>下一步数据要求</h4><ul><li v-for="text in observed.missing_data" :key="text">{{text}}</li></ul><p class="muted">先明确同周期、同人群、同渠道的指标口径，再观察转化与复购。不同公开平台互动量不能合并成去重访客UV。</p></article>
 </template>
</section>
</template>

<style scoped>
.gmv{display:grid;gap:22px}.gmv h3{line-height:1.6}.gmv p,.gmv li{font-size:13px;line-height:1.85}.gmv ul{padding-left:22px}.controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.gmv .panel-heading{flex-wrap:wrap;gap:12px}.gmv-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}.gmv-stats article{display:grid;gap:12px}.gmv-stats strong{font-size:25px;color:#36543a;overflow-wrap:anywhere}.gmv-stats small,.gmv-stats span{font-size:12px;color:#637168}.formula{font-size:18px!important;font-weight:600;color:#36543a}.warning-note{background:#fff6e6;border-left:3px solid #be903c;padding:12px 18px;color:#725621}.error-note{color:#a23932}.contributions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}.contributions>div{display:grid;gap:10px;background:#f2f6ef;padding:18px}.contributions span{font-size:12px;color:#637168}.contributions strong{font-size:23px;color:#36543a}.input-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:20px 0}.input-grid label{display:grid;gap:7px;font-size:12px;color:#54655a}.gmv input,.gmv select{padding:10px;border:1px solid #dfe7df;border-radius:7px;background:white;max-width:100%;box-sizing:border-box}.gmv summary{padding:14px 0;cursor:pointer;font-size:13px}.inset{padding:0 24px}.gmv h4{font-size:14px;margin:20px 0 8px}@media(max-width:1100px){.gmv-stats{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:650px){.input-grid,.contributions{grid-template-columns:1fr}}
</style>
