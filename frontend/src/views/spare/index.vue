<template>
  <section class="page" data-module="spare">
    <header class="page-head">
      <div>
        <h2>器材领用管理</h2>
        <p class="page-desc">维护器材领用单，围绕领用单号、器材名称、器材规格、领用数量做登记、筛选与状态流转。更换器材记录按所属工区归属管理，跨工区账号只读可见。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记器材领用单</button>
        <button class="btn" type="button" @click="exportRows">导出器材领用清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>当前状态</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td>{{ row.status ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              :disabled="!canRun(row)"
              :title="actionHint(row)"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">暂无器材领用数据，可先登记器材领用单</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条器材领用记录（当前账号：{{ session.operator }} · {{ session.role }} · {{ session.section }}）</span>
      <span v-if="actionMessage" :class="actionOk ? 'ok-text' : 'error-text'">{{ actionMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/spare'
const columns = ["领用单号", "器材名称", "器材规格", "领用数量", "领用人员", "领用日期", "所属工区", "领用状态"]
const actions = ["批准领用", "确认发放", "退回器材"]
const statuses = ["待审批", "已批准", "已领用", "已退回"]
const stats = [{"label": "待审批领用", "value": 0}, {"label": "本月领用单", "value": 0}, {"label": "退回单数", "value": 0}]

const session = useSessionStore()
const rows = ref<Row[]>([])
const total = ref(0)
const actionMessage = ref('')
const actionOk = ref(true)
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  actionOk.value = false
  actionMessage.value = '器材领用单登记入口尚未接入审批流'
}

function belongsToCurrentSection(row: Row) {
  return row['所属工区'] === session.section
}

function canRun(row: Row) {
  return belongsToCurrentSection(row)
}

function actionHint(row: Row) {
  if (!belongsToCurrentSection(row)) {
    return `该记录归属${row['所属工区'] ?? '其他工区'}，当前账号属于${session.section}，跨工区只读`
  }
  return ''
}

async function runAction(action: string, row: Row) {
  if (!canRun(row)) {
    return
  }
  actionMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    actionOk.value = Boolean(payload.ok)
    actionMessage.value = payload.message ?? (payload.ok ? '操作完成' : '操作被拒绝')
    if (payload.ok) {
      await reload()
    }
  } catch (error) {
    actionOk.value = false
    actionMessage.value = error instanceof Error ? error.message : '器材领用操作失败'
  }
}

async function reload() {
  actionMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('器材领用单列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    actionOk.value = false
    actionMessage.value = error instanceof Error ? error.message : '器材领用列表读取失败'
  }
}

onMounted(reload)
</script>
