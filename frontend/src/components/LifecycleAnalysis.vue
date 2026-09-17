<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import DataTable from './DataTable.vue'
const report=ref(null), error=ref(''), loading=ref(false), query=ref(''), stage=ref(''), selected=ref(''), asOf=ref('')
const page=ref(1), detailPanel=ref(null)
const rows=computed(()=>report.value?.operators.filter(r=>(!query.value||r.operator.toLowerCase().includes(query.value.toLowerCase()))&&(!stage.value||r.stage===stage.value))||[])
const pageRows=computed(()=>rows.value.slice((page.value-1)*10,page.value*10))
watch([query,stage],()=>page.value=1)
async function selectRole(row){selected.value=row.operator;await nextTick();detailPanel.value?.scrollIntoView({behavior:'smooth',block:'start'})}
const role=computed(()=>report.value?.operators.find(r=>r.operator===selected.value))
const events=computed(()=>report.value?.events.filter(r=>r.operator===selected.value)||[])
const intervals=computed(()=>report.value?.snapshot_deltas.filter(r=>r.operators.includes(selected.value))||[])
const windows=computed(()=>report.value?.event_windows.filter(r=>r.operator===selected.value)||[])
const weekly=computed(()=>report.value?.weekly.filter(r=>r.operator===selected.value)||[])
const params=computed(()=>asOf.value?'&as_of='+encodeURIComponent(asOf.value):'')
const safeUrl=url=>/^https?:\/\//.test(url||'')?url:null
const count=r=>r.bilibili_content_in_sample+r.weibo_content_in_sample
async function load(){
 loading.value=true;error.value=''
 try{const response=await fetch('/api/lifecycle'+(asOf.value?'?as_of='+encodeURIComponent(asOf.value):''));const data=await response.json();if(!response.ok)throw Error(data.detail||'读取失败');report.value=data;if(!data.operators.some(r=>r.operator===selected.value))selected.value=data.operators.find(r=>r.stage==='事件观察期')?.operator||data.operators[0]?.operator}
 catch(e){error.value=e.message;report.value=null}finally{loading.value=false}
}
onMounted(load)
defineExpose({reload:load})
</script>

<template>
<section class="lifecycle">
  <article class="panel">
    <div class="panel-heading"><div><h3>从选品排序到分阶段观察</h3><p>用事件时间、直接内容与连续复采，判断现有证据能支持什么决策。</p></div></div>
    <div class="controls"><label>分析截至日期<input type="date" v-model="asOf"/></label><button class="button white" :disabled="loading" @click="load">{{loading?'分析中…':'重新分析'}}</button><span class="muted">留空使用最近采集日</span><a class="button white" :href="'/api/lifecycle?download=markdown'+params">导出报告</a><a class="button white" :href="'/api/lifecycle?download=json'+params">下载完整证据</a></div>
    <p v-if="error" role="alert">{{error}}</p><p v-if="loading" role="status">正在核对事件和复采区间…</p>
  </article>
  <template v-if="report">
    <div class="lifecycle-stats"><article class="panel"><span>角色覆盖</span><strong>{{report.summary.operator_count}}</strong><small>{{report.summary.operators_with_direct_content}} 名有直接内容</small></article><article class="panel"><span>角色周记录</span><strong>{{report.summary.weekly_rows}}</strong><small>派生记录，不是新增采集量</small></article><article class="panel"><span>角色直接内容复采区间</span><strong>{{report.summary.direct_content_intervals}}</strong><small>同一内容的两次累计计数之差</small></article><article class="panel"><span>达到连续趋势门槛</span><strong>{{report.summary.trend_ready_operators}}</strong><small>不足时保留“待验证”</small></article></div>
    <article class="panel"><h3>数据截至 {{report.as_of}} · 阶段与热度分开判断</h3><p class="muted spaced">近期宣传可以确定观察窗口，不能直接证明升温；旧内容也不等于衰退。当前阶段标签以已收录事件为依据，问卷与商品横截面不参与趋势判定。</p><div class="controls"><span class="badge" v-for="(n,label) in report.summary.stage_counts" :key="label">{{label}} {{n}}</span></div></article>
    <article class="panel table-panel"><div class="panel-heading"><h3>{{report.summary.operator_count}}名候选角色 · 生命周期证据</h3><div class="controls"><input v-model="query" aria-label="搜索角色" placeholder="搜索角色"/><select v-model="stage" aria-label="筛选阶段"><option value="">全部阶段</option><option v-for="(_,label) in report.summary.stage_counts" :key="label">{{label}}</option></select></div></div><DataTable :rows="pageRows" action="查看依据" @select="selectRole" :columns="[{key:'operator',label:'角色'},{key:'stage',label:'事件阶段',type:'badge'},{key:'content_signal',label:'内容趋势'},{key:'last_direct_publication',label:'最近直接内容'},{key:'direct_content_count',label:'内容数',type:'number'},{key:'snapshot_interval_count',label:'复采区间',type:'number'}]"/><div class="controls page-control"><span>共 {{rows.length}} 名 · 第 {{page}} / {{Math.max(1,Math.ceil(rows.length/10))}} 页</span><button class="button white" :disabled="page<=1" @click="page--">上一页</button><button class="button white" :disabled="page*10>=rows.length" @click="page++">下一页</button></div></article>
    <article v-if="role" ref="detailPanel" class="panel" aria-live="polite"><div class="panel-heading"><h3>{{role.operator}} · 结论与下一步</h3><select v-model="selected" aria-label="查看角色详情"><option v-for="r in report.operators" :key="r.operator">{{r.operator}}</option></select></div><p>{{role.stage_reason}}</p><p class="muted spaced">内容信号：{{role.content_signal}}。{{role.signal_reason}}</p><p class="muted">缺口：{{role.evidence_gaps}}</p><p class="action-note">建议：{{role.next_action}}</p><p class="muted">最近复采：{{role.last_capture||'缺失'}} · {{role.stale_observation?'需要补采':'仍在'+report.policy.trend_window_days+'日观察时效内'}}；问卷提及 {{role.survey_mentions??'缺失'}}，仅作横截面背景。</p>
      <h4>近{{report.policy.weekly_history}}周 · 样本内直接内容发布时间轴</h4><div class="weeks"><div v-for="w in weekly" :key="w.week_start" :title="w.week_start+'：'+count(w)+'条；'+w.coverage"><span>{{count(w)||''}}</span><i :style="{height:Math.max(3,Math.min(count(w)*24,72))+'px'}"></i><small>{{w.week_start.slice(5)}}</small></div></div><p class="muted">0表示该周未收录直接内容；不表示角色没有关注。共享活动流量未归为直接内容。</p>
      <h4>直接事件来源</h4><ul class="sources"><li v-for="e in events" :key="e.event_id"><a v-if="safeUrl(e.source_url)" :href="e.source_url" target="_blank" rel="noopener">{{e.title||e.event_type}}</a><span v-else>{{e.title||e.event_type}}</span> · {{e.event_at.slice(0,10)}}<small>{{e.basis||e.evidence_note}}</small></li></ul><p v-if="!events.length" class="muted">尚无直接事件证据，请补充官方上线或活动公告。</p>
      <h4>复采增量（不同区间与内容年龄不直接排名）</h4><DataTable :rows="intervals" :columns="[{key:'content_id',label:'内容ID'},{key:'start',label:'前次采集'},{key:'end',label:'后次采集'},{key:'interval_days',label:'间隔天数',type:'number'},{key:'view_delta',label:'播放增量',type:'number'},{key:'views_per_day',label:'区间日均增量',type:'number'},{key:'status',label:'校验状态'}]"/>
      <details><summary>事件前后{{report.policy.observation_window_days}}天样本窗口</summary><DataTable :rows="windows" :columns="[{key:'event_date',label:'事件日期'},{key:'pre_other_content_in_sample',label:'前窗口其他内容',type:'number'},{key:'post_other_content_in_sample',label:'后窗口其他内容',type:'number'},{key:'comparison_status',label:'可解释范围'}]"/><p class="muted">排除作为事件锚点的内容本身。窗口内零条不等于真实零曝光；不计算需求提升率。</p></details>
    </article>
    <article class="panel"><h3>判定规则与证据边界</h3><p class="muted spaced">事件窗口 {{report.policy.observation_window_days}} 天；趋势需要至少 {{report.policy.trend_min_content}} 条相同内容的 {{report.policy.trend_min_intervals}} 个连续 {{report.policy.trend_window_days}} 日区间，变化阈值 {{report.policy.trend_change_threshold*100}}%。这些是可调整的探索规则，不是经过销量验证的标准。</p><ul class="sources"><li v-for="text in report.limitations" :key="text">{{text}}</li></ul><details><summary>输入指纹与复现依据</summary><DataTable :rows="report.manifest" :columns="[{key:'file',label:'输入文件'},{key:'sha256',label:'SHA-256'}]"/></details></article>
  </template>
</section>
</template>

<style scoped>
.lifecycle{display:grid;gap:22px}.controls{display:flex;align-items:center;flex-wrap:wrap;gap:12px}.controls label{display:flex;align-items:center;gap:9px;font-size:13px}.lifecycle input,.lifecycle select{padding:9px;border:1px solid #dfe7df;border-radius:7px;background:white;max-width:240px}.lifecycle-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}.lifecycle-stats article{display:grid;gap:10px}.lifecycle-stats strong{font-size:30px;color:#36543a}.lifecycle-stats span,.lifecycle-stats small{font-size:12px;color:#637168}.lifecycle p{line-height:1.85;font-size:13px}.action-note{padding:12px;background:#f2f6ef;border-left:3px solid #70946f}.lifecycle h4{font-size:14px;margin:24px 0 12px}.sources{font-size:13px;line-height:1.9;padding-left:20px}.sources small{display:block;color:#637168}.sources a{color:#3f6949}.weeks{display:flex;gap:8px;overflow-x:auto;padding:12px 0}.weeks>div{min-width:34px;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;height:115px}.weeks i{display:block;width:20px;background:#70946f;border-radius:3px}.weeks small{font-size:9px;margin-top:8px;color:#637168}.weeks span{font-size:11px;color:#3f6949}.lifecycle summary{cursor:pointer;padding:14px 0;font-size:13px}.lifecycle .panel-heading{flex-wrap:wrap;gap:12px}@media(max-width:1000px){.lifecycle-stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
.weeks{gap:4px}.weeks>div{min-width:24px;flex:1}.page-control{padding:16px 24px;font-size:12px}
</style>
