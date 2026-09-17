<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { Plus, Download, RefreshCw, ClipboardList, ArrowUpRight, X } from 'lucide-vue-next'

const emit = defineEmits(['navigate'])
const labels = { todo: '待处理', in_progress: '处理中', blocked: '待协助', done: '已完成' }
const categories = ['商品维护', 'ERP核对', '用户调研', '直播准备', '临时事务']
const data = ref({items: [], total: 0, counts: {}, overdue_count: 0})
const filters = ref({q: '', status: '', category: '', overdue: false})
const appliedQuery = ref('')
const loading = ref(false), saving = ref(false), error = ref(''), notice = ref('')
const form = ref(null), selected = ref(null), history = ref([]), formError = ref('')
const dialog = ref(null)
let returnFocus = null
const filterQuery = () => new URLSearchParams(Object.entries(filters.value).filter(([,v])=>v !== '' && v !== false)).toString()
const exportUrl = computed(()=>'/api/operations/tasks/export?' + appliedQuery.value)
async function api(path='', options={}) {
  const response = await fetch('/api/operations/tasks'+path, {...options, headers: {'Content-Type':'application/json'}})
  const result = await response.json()
  if(!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : '请检查标题、工作内容、验收要求和日期格式')
  return result
}
let request = 0
async function load() {
  const token = ++request
  loading.value = true; error.value = ''
  try { const query=filterQuery(); const result = await api('?' + query); if(token === request) { data.value = result; appliedQuery.value=query } }
  catch(e) { if(token === request) error.value = e.message }
  finally { if(token === request) loading.value = false }
}
async function seed(path) {
  saving.value = true; error.value = ''; notice.value = ''
  try {
    const result = await api(path, {method:'POST'})
    notice.value = path === '/from-brief' ? `新增 ${result.created.length} 条待办，保留 ${result.existing_count} 条已有记录。已完成事项也不会重复生成。` : '已建立直播准备演练待办，请补充负责人、日期和实际核对记录。'
    filters.value = {q:'',status:'',category:'',overdue:false}; await load()
  } catch(e) { error.value = e.message } finally { saving.value = false }
}
async function edit(task=null) {
  returnFocus = document.activeElement
  selected.value = task; history.value = []; formError.value = ''
  form.value = task ? Object.fromEntries(['title','category','description','acceptance','assignee','due_date','priority','version','status'].map(key=>[key,task[key]])) : {title:'',category:'临时事务',description:'',acceptance:'',assignee:'',due_date:'',priority:'P1'}
  await nextTick()
  dialog.value?.querySelector('input')?.focus()
  if(task) {
    form.value.note = ''
    try { const result=await api('/'+task.id+'/history'); if(selected.value?.id===task.id) history.value=result.items }
    catch(e) { formError.value=e.message }
  }
}
function close() { if(!saving.value) { form.value=null; selected.value=null; returnFocus?.focus() } }
function trapFocus(event) {
  if(event.key !== 'Tab') return
  const nodes = [...dialog.value.querySelectorAll('button:not(:disabled), input, select, textarea, summary')].filter(el=>el.getClientRects().length)
  if(event.shiftKey && document.activeElement === nodes[0]) { event.preventDefault(); nodes.at(-1)?.focus() }
  else if(!event.shiftKey && document.activeElement === nodes.at(-1)) { event.preventDefault(); nodes[0]?.focus() }
}
async function save() {
  saving.value=true; formError.value=''
  try {
    const body={...form.value,due_date:form.value.due_date||null}
    await api(selected.value ? '/'+selected.value.id : '', {method:selected.value?'PATCH':'POST',body:JSON.stringify(body)})
    form.value=null; selected.value=null; notice.value='待办已保存，交接记录可在处理历史中查看。'; await load()
  } catch(e) { formError.value=e.message } finally { saving.value=false }
}
onMounted(load)
</script>

<template>
  <div class="operations-tasks">
    <div class="section-notice"><ClipboardList :size="18"/><span>登记事项、跟进进度和记录交接。分析建议转成待办后，仍需实际核对与执行。</span></div>
    <div class="toolbar task-actions">
      <div class="toolbar-actions"><button class="button primary" :disabled="saving" @click="edit()"><Plus :size="16"/>登记事项</button><button class="button white" :disabled="saving" @click="seed('/from-brief')">从运营简报建立待办</button><button class="button white" :disabled="saving" @click="seed('/live-checklist')">直播准备清单</button></div>
      <div class="toolbar-actions"><a class="button white" :href="exportUrl"><Download :size="15"/>导出交接表 CSV</a><button class="button white" :disabled="loading" @click="load"><RefreshCw :size="15"/>刷新</button></div>
    </div>
    <p v-if="notice" class="task-notice" role="status">{{notice}}</p>
    <p v-if="error" class="error-banner" role="alert">{{error}}</p>
    <section class="task-stats" aria-label="当前筛选统计">
      <article v-for="(label,key) in labels" :key="key"><span>{{label}}</span><strong>{{data.counts[key]||0}}</strong></article>
      <article><span>未完成且逾期</span><strong :class="{'overdue-text':data.overdue_count}">{{data.overdue_count}}</strong></article>
    </section>
    <section class="panel task-list">
      <form class="task-filters" @submit.prevent="load">
        <label>搜索<input v-model="filters.q" placeholder="事项、负责人或记录" type="search"/></label>
        <label>工作类别<select v-model="filters.category"><option value="">全部类别</option><option v-for="item in categories" :key="item">{{item}}</option></select></label>
        <label>状态<select v-model="filters.status"><option value="">全部状态</option><option v-for="(label,key) in labels" :key="key" :value="key">{{label}}</option></select></label>
        <label class="check-filter"><input type="checkbox" v-model="filters.overdue"/>只看逾期</label><button class="button primary" :disabled="loading">筛选</button>
      </form>
      <div class="task-table-meta"><span>当前筛选 {{data.total}} 条 · 统计和交接表按同一筛选口径</span><span>CSV 可用 Excel 打开</span></div>
      <p v-if="loading" role="status">正在读取待办…</p>
      <div v-if="!loading&&!data.total" class="task-empty"><ClipboardList :size="36"/><h3>暂无符合条件的待办</h3><p>从运营简报建立首批任务，或登记一项临时工作。</p></div>
      <div v-else class="task-table-wrap"><table><thead><tr><th>事项与来源</th><th>负责人 / 截止日期</th><th>进度</th><th>最新交接记录</th><th>操作</th></tr></thead><tbody>
        <tr v-for="task in data.items" :key="task.id"><td><div class="task-title"><span class="badge gray">{{task.priority}}</span><b>{{task.title}}</b></div><p>{{task.category}}</p><small>{{task.nature}}</small></td><td><b>{{task.assignee||'待分配'}}</b><p :class="{'overdue-text':task.overdue}">{{task.due_date||'未设截止日期'}}{{task.overdue?' · 逾期':''}}</p></td><td><span class="task-status" :class="task.status">{{task.status_label}}</span></td><td class="task-note">{{task.note||'尚无处理记录'}}</td><td><button class="text-button" @click="edit(task)">处理 / 记录</button><button v-if="task.target" class="text-button" @click="emit('navigate',task.target)">查看依据<ArrowUpRight :size="13"/></button></td></tr>
      </tbody></table></div>
    </section>
    <p class="task-footnote">截止日期按北京时间判断。完成状态由使用者登记；任务来源及数据性质保留在记录中。导出范围为当前筛选，不含历史记录全文。</p>
    <div v-if="form" class="task-dialog-backdrop" @click.self="close" @keydown.esc="close" @keydown="trapFocus">
      <section ref="dialog" class="task-dialog" role="dialog" aria-modal="true" aria-labelledby="task-dialog-title">
        <header><h2 id="task-dialog-title">{{selected?'处理待办与交接':'登记运营事项'}}</h2><button class="icon-btn" @click="close" :disabled="saving" aria-label="关闭待办编辑"><X :size="20"/></button></header>
        <p v-if="selected" class="task-source">{{selected.nature}}<br/>来源：{{selected.source}}</p>
        <form @submit.prevent="save">
          <div class="task-form-grid">
            <label class="full">事项标题<input v-model="form.title" required minlength="2" maxlength="120"/></label>
            <label>工作类别<select v-model="form.category"><option v-for="item in categories" :key="item">{{item}}</option></select></label>
            <label>优先级<select v-model="form.priority"><option>P0</option><option>P1</option><option>P2</option></select></label>
            <label>负责人<input v-model="form.assignee" maxlength="80" :required="['in_progress','done'].includes(form.status)" placeholder="填写实际跟进人"/></label>
            <label>截止日期<input type="date" v-model="form.due_date"/></label>
            <label class="full">工作内容<textarea v-model="form.description" required minlength="3" maxlength="4000" rows="4"/></label>
            <label class="full">验收要求<textarea v-model="form.acceptance" required minlength="3" maxlength="1500" rows="3" placeholder="需要核对什么、输出哪些记录"/></label>
            <label v-if="selected">处理状态<select v-model="form.status"><option v-for="(label,key) in labels" :key="key" :value="key">{{label}}</option></select></label>
            <label v-if="selected" class="full">本次进展与交接说明<textarea v-model="form.note" required :minlength="['blocked','done'].includes(form.status)?10:3" maxlength="2000" rows="3" placeholder="待协助：原因及所需支持；已完成：处理结果及核对依据（至少10字）"/></label>
          </div>
          <p v-if="formError" class="error-banner" role="alert">{{formError}}</p>
          <footer><button type="button" class="button white" @click="close" :disabled="saving">取消</button><button class="button primary" :disabled="saving">{{saving?'保存中…':'保存待办'}}</button></footer>
        </form>
        <details v-if="selected" class="task-history"><summary>处理历史（{{history.length}}条）</summary><article v-for="item in history" :key="item.audit_id"><b>{{item.changed_at}} · {{labels[item.after.status]}}</b><p>{{item.note}}</p><small>负责人：{{item.after.assignee||'待分配'}} · 截止：{{item.after.due_date||'未设置'}} · 版本 {{item.after.version}}</small></article></details>
      </section>
    </div>
  </div>
</template>

<style scoped>
.task-actions,.task-filters{flex-wrap:wrap;gap:12px}.task-actions .toolbar-actions{flex-wrap:wrap}.task-notice{padding:12px 16px;background:#eef6f3;color:#25634f;border-radius:8px;font-size:13px}.task-stats{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin:20px 0}.task-stats article{padding:18px;background:white;border:1px solid #e6eae8;border-radius:12px}.task-stats span{display:block;font-size:13px;color:#6a7471}.task-stats strong{display:block;font-size:27px;margin-top:9px}.overdue-text{color:#ad4a27!important}.task-list{padding:20px}.task-filters{display:flex;align-items:end}.task-filters label,.task-form-grid label{display:flex;flex-direction:column;gap:7px;font-size:13px;color:#47554f}.task-filters input,.task-filters select,.task-form-grid input,.task-form-grid select,.task-form-grid textarea{border:1px solid #d6dfdb;border-radius:7px;padding:10px 12px;font:inherit;background:white;color:#253b32;min-width:0}.task-filters .check-filter{flex-direction:row;align-items:center;align-self:center;margin-top:20px}.task-filters input[type=checkbox]{width:16px;height:16px}.task-table-meta{display:flex;justify-content:space-between;gap:12px;color:#738078;font-size:12px;margin:22px 0 12px}.task-table-wrap{overflow-x:auto}.task-table-wrap table{border-collapse:collapse;width:100%;min-width:860px;text-align:left;font-size:13px}.task-table-wrap th{color:#65736c;background:#f5f7f6;padding:12px;font-weight:500}.task-table-wrap td{padding:18px 12px;vertical-align:top;border-bottom:1px solid #edf0ee}.task-table-wrap td:first-child{width:32%;min-width:240px}.task-table-wrap td:nth-child(2){min-width:150px}.task-table-wrap td:last-child{min-width:108px}.task-title{display:flex;align-items:start;gap:8px;line-height:1.6}.task-table-wrap p{margin:8px 0;font-size:12px}.task-table-wrap small{color:#7c8781;font-size:11px}.task-note{white-space:pre-wrap;overflow-wrap:anywhere;max-width:270px;line-height:1.7}.task-status{display:inline-block;padding:5px 9px;white-space:nowrap;border-radius:5px;background:#edf0f2;color:#556370;font-size:12px}.task-status.in_progress{background:#eaf2fc;color:#356495}.task-status.blocked{background:#fff1df;color:#9a601c}.task-status.done{background:#e5f2eb;color:#2e7954}.task-table-wrap .text-button{display:flex;margin:0 0 12px}.task-empty{text-align:center;padding:50px 15px;color:#748079}.task-empty svg{margin:auto}.task-empty h3{font-size:16px;margin:16px 0 8px}.task-empty p,.task-footnote{font-size:12px;color:#78837e;line-height:1.8}.task-dialog-backdrop{position:fixed;inset:0;z-index:110;background:#10251e66;display:flex;align-items:center;justify-content:center;padding:24px}.task-dialog{background:white;border-radius:16px;width:680px;max-height:90vh;overflow:auto;padding:25px}.task-dialog header{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}.task-dialog h2{font-size:20px}.task-source{font-size:12px;line-height:1.8;background:#f3f6f4;padding:12px;color:#65736c}.task-form-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:18px}.task-form-grid .full{grid-column:1/-1}.task-form-grid textarea{resize:vertical;line-height:1.7}.task-dialog footer{display:flex;justify-content:end;gap:10px;margin-top:20px}.task-history{border-top:1px solid #e6eae8;margin-top:22px;padding-top:16px;font-size:13px}.task-history article{padding:12px 0;border-bottom:1px solid #edf0ee}.task-history p{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.7}.task-history small{color:#738078}.task-history summary{cursor:pointer}@media(max-width:700px){.task-stats{grid-template-columns:repeat(2,1fr);gap:8px}.task-stats article{padding:12px}.task-filters label{flex:1;min-width:130px}.task-table-meta{flex-direction:column}.task-dialog-backdrop{padding:10px}.task-dialog{padding:18px;max-height:94vh}.task-form-grid{grid-template-columns:1fr}.task-list{padding:14px}.task-actions .button{font-size:12px}}
</style>
