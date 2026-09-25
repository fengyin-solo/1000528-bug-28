<template>
  <section class="page" data-module="dispose">
    <header class="page-head">
      <div>
        <h2>故障处置管理</h2>
        <p class="page-desc">维护处置单，围绕处置单号、关联故障、处置措施、更换器材做登记、筛选与状态流转。确认验收仅本工区验收人员可提交，其他人只读可见。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记处置单</button>
        <button class="btn" type="button" @click="exportRows">导出故障处置清单</button>
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
              :disabled="!canRun(action, row)"
              :title="actionHint(action, row)"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">暂无故障处置数据，可先登记处置单</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条故障处置记录（当前账号：{{ session.operator }} · {{ session.role }} · {{ session.section }}）</span>
      <span v-if="actionMessage" :class="actionOk ? 'ok-text' : 'error-text'">{{ actionMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/dispose'
const columns = ["处置单号", "关联故障", "处置措施", "更换器材", "处置人员", "完成时间", "所属工区", "验收人员"]
const actions = ["受理处置", "提交验收", "确认验收"]
const statuses = ["待受理", "处置中", "待验收", "已验收"]
const stats = [{"label": "待受理处置", "value": 0}, {"label": "处置中单据", "value": 0}, {"label": "本月验收单数", "value": 0}]

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
  actionMessage.value = '处置单登记入口尚未接入审批流'
}

function isAccepted(row: Row) {
  return row.status === '已验收'
}

function canRun(action: string, row: Row) {
  if (isAccepted(row)) {
    return false
  }
  // 受理处置、提交验收照旧；确认验收只放开给本工区验收人员，其余人等只读
  if (action === '确认验收') {
    return session.role === '验收人员' && row['所属工区'] === session.section && row.status === '待验收'
  }
  return true
}

function actionHint(action: string, row: Row) {
  if (isAccepted(row)) {
    return '该处置单已完成验收，无需重复提交'
  }
  if (action === '确认验收') {
    if (session.role !== '验收人员') {
      return `确认验收仅验收人员可提交（当前角色：${session.role}）`
    }
    if (row['所属工区'] !== session.section) {
      return `处置单归属${row['所属工区'] ?? '其他工区'}，跨工区不能确认验收`
    }
    if (row.status !== '待验收') {
      return '处置单需先提交验收、进入待验收后才能确认'
    }
  }
  return ''
}

async function runAction(action: string, row: Row) {
  if (!canRun(action, row)) {
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
    actionMessage.value = error instanceof Error ? error.message : '故障处置操作失败'
  }
}

async function reload() {
  actionMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('处置单列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    actionOk.value = false
    actionMessage.value = error instanceof Error ? error.message : '故障处置列表读取失败'
  }
}

onMounted(reload)
</script>
