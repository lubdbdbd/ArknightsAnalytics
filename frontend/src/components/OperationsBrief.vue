<script setup>
import { ArrowUpRight, Download } from 'lucide-vue-next'
defineProps({ brief: Object })
defineEmits(['navigate'])
</script>

<template>
  <section v-if="brief" class="panel operations-brief">
    <div class="panel-heading"><div><h3>运营简报 · 从数据到具体工作</h3><p>{{ brief.method }}</p></div><a class="button white" href="/api/operations/brief?download=true"><Download :size="14"/>导出简报</a></div>
    <div class="brief-grid">
      <article v-for="task in brief.tasks" :key="task.id" class="brief-card">
        <span class="badge gray">{{ task.nature }}</span><h4>{{ task.title }}</h4>
        <p><b>发现</b>{{ task.finding }}</p><p><b>建议动作</b>{{ task.action }}</p>
        <details><summary>查看核对标准与依据</summary><p>{{ task.acceptance }}</p><small>{{ task.source }}</small></details>
        <button class="text-button" @click="$emit('navigate',task.target)">进入工作模块 <ArrowUpRight :size="14"/></button>
      </article>
    </div>
    <button class="text-button" @click="$emit('navigate','tasks')">进入日常运营待办，登记进度与交接 <ArrowUpRight :size="14"/></button>
    <p class="muted brief-boundary">{{ brief.scope_note }}</p>
  </section>
</template>
