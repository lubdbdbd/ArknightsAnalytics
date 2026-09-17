<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { RefreshCw, Download, ShieldCheck, X } from 'lucide-vue-next'
import DataTable from './DataTable.vue'

const report = ref(null), busy = ref(false), error = ref(''), detail = ref(null)
const dialog = ref(null)
let returnFocus = null
watch(detail, async value=>{if(value){returnFocus=document.activeElement;await nextTick();dialog.value?.querySelector('button')?.focus()}else{returnFocus?.focus()}})
const scenario = ref('snapshot'), severity = ref(''), rule = ref(''), page = ref(1)
const applied = ref(''), appliedScenario = ref('snapshot')
const columns = [{key:'domain',label:'业务域'},{key:'rule',label:'核对规则'},{key:'record_id',label:'关联记录',class:'primary-cell'},
 {key:'source_row',label:'源行号',type:'number'},{key:'severity_label',label:'级别'},{key:'action',label:'复核建议',class:'wide-cell'}]
const totalPages = computed(()=>Math.max(1,Math.ceil((report.value?.issue_total||0)/30)))
const exportUrl = computed(()=>'/api/erp/checks?'+applied.value+'&download=true')
let request = 0
async function load(reset=false) {
  if(reset) page.value=1
  busy.value=true; error.value=''
  const token=++request
  const query=new URLSearchParams({scenario:scenario.value,page:String(page.value),limit:'30'})
  if(severity.value)query.set('severity',severity.value)
  if(rule.value)query.set('rule',rule.value)
  try {
    const response=await fetch('/api/erp/checks?'+query)
    const body=await response.json()
    if(!response.ok)throw Error(typeof body.detail==='string'?body.detail:'核对请求失败')
    if(token===request){report.value=body; applied.value=query.toString(); appliedScenario.value=body.scenario}
  } catch(e) {if(token===request)error.value=e.message} finally {if(token===request)busy.value=false}
}
function changeScenario() { severity.value='';rule.value='';load(true) }
function movePage(delta) {page.value+=delta;load()}
onMounted(()=>load())
</script>

<template>
  <section class="erp-checks">
    <div class="check-intro"><div><h3>先核对业务数据，再解释经营结果</h3><p>检查订单、SKU、库存、采购与售后之间的关联，保留源表行号与复核依据。</p></div><ShieldCheck :size="25"/></div>
    <div class="toolbar check-toolbar">
      <label>核对数据<select v-model="scenario" @change="changeScenario" :disabled="busy" aria-label="ERP核对数据"><option value="snapshot">原始模拟ERP快照</option><option value="demo">异常演练（内存副本）</option></select></label>
      <div class="toolbar-actions"><button class="button white" @click="load(true)" :disabled="busy"><RefreshCw :size="15"/>重新核对</button><a v-if="report" class="button primary" :href="exportUrl" :aria-disabled="busy" @click="busy&&$event.preventDefault()"><Download :size="15"/>导出复核清单 CSV</a></div>
    </div>
    <p v-if="error" class="error-banner" role="alert">{{error}}</p><p v-if="busy" class="check-progress" role="status">正在逐项核对ERP快照…</p>
    <template v-if="report">
      <p class="check-scope" :class="{demo:appliedScenario==='demo'}"><b>{{report.scope}}</b><span>库存快照末日：{{report.as_of||'缺失，无法判断采购逾期'}}。以下统计覆盖全部规则，不随异常列表筛选变化。</span></p>
      <section class="check-metrics"><article><span>核对规则</span><strong>{{report.summary.rule_count}}</strong></article><article><span>数据异常命中</span><strong>{{report.summary.error_count}}</strong></article><article><span>经营跟进提醒</span><strong>{{report.summary.warning_count}}</strong></article><article><span>涉及源记录</span><strong>{{report.summary.affected_records}}</strong></article></section>
      <details v-if="report.injections.length" class="panel check-injections"><summary>本次演练修改了 {{report.injections.length}} 处输入，查看前后值</summary><p>一个输入可能触发多条规则。所有修改仅在内存副本中生效，重新切换原始快照即可对比。</p><DataTable :rows="report.injections" :columns="[{key:'table',label:'源表'},{key:'source_row',label:'源行号',type:'number'},{key:'field',label:'字段'},{key:'before',label:'原值'},{key:'after',label:'演练值'}]"/></details>
      <article class="panel check-results">
        <div class="panel-heading"><div><h3>异常与跟进清单</h3><p>先看关联记录，再查看观测值与核对依据。</p></div><span class="badge gray">当前筛选 {{report.issue_total}} 项</span></div>
        <form class="check-filters" @submit.prevent="load(true)"><label>级别<select v-model="severity" :disabled="busy" aria-label="核对级别"><option value="">全部</option><option value="error">数据异常</option><option value="warning">跟进提醒</option></select></label><label>规则<select v-model="rule" :disabled="busy" aria-label="核对规则"><option value="">全部规则</option><option v-for="item in report.rules" :key="item.code" :value="item.code">{{item.domain}} · {{item.title}}</option></select></label><button class="button white" :disabled="busy">筛选</button></form>
        <DataTable :rows="report.items.map(item=>({...item,entity_id:item.issue_id,severity_label:item.severity==='error'?'数据异常':'跟进提醒'}))" :columns="columns" action="查看依据" @select="detail=$event"/>
        <div class="pagination"><span>CSV导出当前已应用筛选的全部记录，不受分页限制。</span><div><button :disabled="busy||report.page<=1" @click="movePage(-1)">上一页</button><span>{{report.page}} / {{totalPages}}</span><button :disabled="busy||report.page>=totalPages" @click="movePage(1)">下一页</button></div></div>
      </article>
      <details class="panel check-rules"><summary>核对规则与统计口径（{{report.rules.length}}项）</summary><DataTable :rows="report.rules.map(item=>({...item,entity_id:item.code}))" :columns="[{key:'domain',label:'业务域'},{key:'title',label:'核对规则'},{key:'checked_count',label:'检查记录',type:'number'},{key:'issue_count',label:'命中数',type:'number'},{key:'state',label:'状态'},{key:'expected',label:'核对口径',class:'wide-cell'}]"/></details>
      <p v-if="report.rules.some(item=>item.code==='refund_cap'&&item.issue_count)" class="check-scope">发现已关闭退款超过实付金额。请核查优惠分摊及退款归属，复核完成前谨慎使用相关净销售和毛利汇总。历史数据不会因核对操作而自动改写。</p>
      <ul class="check-limitations"><li v-for="item in report.limitations" :key="item">{{item}}</li></ul>
    </template>
    <div v-if="detail" class="check-dialog-backdrop" @click.self="detail=null" @keydown.esc="detail=null">
      <section ref="dialog" class="check-dialog" role="dialog" aria-modal="true" aria-label="ERP异常核对依据" tabindex="-1" @keydown.tab.prevent="dialog.querySelector('button').focus()"><header><h3>{{detail.rule}}</h3><button class="icon-btn" @click="detail=null" aria-label="关闭核对依据"><X :size="20"/></button></header><span class="badge" :class="{amber:appliedScenario==='demo'}">{{report.scope}}</span><dl><dt>关联记录</dt><dd>{{detail.record_id}}</dd><dt>来源位置</dt><dd>{{detail.source_table}}.csv · 第 {{detail.source_row}} 行</dd><dt>观测值</dt><dd class="observed">{{detail.observed}}</dd><dt>核对依据</dt><dd>{{detail.expected}}</dd><dt>下一步复核</dt><dd>{{detail.action}}</dd></dl><p>需要协助时，可在“日常运营待办”登记该记录编号、问题及所需支持。</p></section>
    </div>
  </section>
</template>

<style scoped>
.check-intro{display:flex;align-items:center;justify-content:space-between;margin:14px 0 22px}.check-intro h3{font-size:18px;margin:0 0 8px}.check-intro p,.check-results p{color:#77837b;font-size:13px;margin:0;line-height:1.8}.check-intro svg{color:#387762}.check-toolbar{align-items:end;gap:15px;flex-wrap:wrap}.check-toolbar label,.check-filters label{display:flex;flex-direction:column;gap:8px;font-size:13px;color:#52645a}.erp-checks select{padding:10px 12px;border:1px solid #d5dfd8;border-radius:7px;background:white;color:#304e3e;font:inherit;max-width:100%}.check-scope{padding:16px 18px;background:#edf3ef;border-radius:8px;font-size:13px;line-height:1.8}.check-scope span{display:block;color:#6b7c70}.check-scope.demo{background:#fff1df;color:#895d21}.check-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:20px 0}.check-metrics article{padding:18px 22px;background:#fff;border:1px solid #e4eae6;border-radius:12px}.check-metrics span{display:block;color:#728078;font-size:13px}.check-metrics strong{display:block;font-size:28px;margin-top:10px}.check-results,.check-injections,.check-rules{padding:22px;margin:18px 0}.check-filters{display:flex;gap:14px;align-items:end;flex-wrap:wrap;margin-bottom:20px}.check-rules summary,.check-injections summary{cursor:pointer;font-weight:600;font-size:14px}.check-rules .table-wrap{margin-top:20px}.check-injections p,.check-limitations{color:#7b847f;font-size:12px;line-height:1.9}.check-progress{font-size:13px;color:#3c7962}.check-dialog-backdrop{position:fixed;inset:0;background:#19332770;display:flex;align-items:center;justify-content:center;z-index:110;padding:20px}.check-dialog{background:white;border-radius:14px;width:680px;max-height:90vh;overflow:auto;padding:28px}.check-dialog header{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}.check-dialog dt{font-size:12px;color:#77887d;margin:20px 0 8px}.check-dialog dd{margin:0;font-size:14px;line-height:1.8;overflow-wrap:anywhere}.check-dialog .observed{padding:12px;background:#f4f6f4;border-radius:6px}.check-dialog p{font-size:12px;color:#718277;line-height:1.9}.check-limitations{padding-left:18px}@media(max-width:700px){.check-metrics{grid-template-columns:1fr 1fr;gap:8px}.check-metrics article{padding:14px}.check-results,.check-rules,.check-injections{padding:14px}.check-filters label{max-width:100%}.check-toolbar .toolbar-actions{flex-wrap:wrap}.check-dialog{padding:20px}}
</style>
