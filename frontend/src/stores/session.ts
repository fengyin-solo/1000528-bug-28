import { defineStore } from 'pinia'

export interface Account {
  name: string
  role: string
  section: string
}

/** 可切换账号，与后端 app/identity.py 内置账号表保持一致 */
export const ACCOUNTS: Account[] = [
  { name: '值班管理员', role: '管理员', section: '信号一工区' },
  { name: '李处置', role: '处置人员', section: '信号一工区' },
  { name: '王验收', role: '验收人员', section: '信号一工区' },
  { name: '赵验收', role: '验收人员', section: '信号二工区' },
  { name: '孙处置', role: '处置人员', section: '信号二工区' },
]

export const OPERATOR_STORAGE_KEY = 'session-operator'

function initialOperator(): string {
  const saved = localStorage.getItem(OPERATOR_STORAGE_KEY)
  if (saved && ACCOUNTS.some((item) => item.name === saved)) {
    return saved
  }
  return ACCOUNTS[0].name
}

export const useSessionStore = defineStore('session', {
  state: () => ({
    operator: initialOperator(),
    shiftLabel: '白班 08:00-20:00',
    scope: '轨道交通信号设备检修平台',
  }),
  getters: {
    canOperate: (state) => state.operator.length > 0,
    account(state): Account {
      return ACCOUNTS.find((item) => item.name === state.operator) ?? ACCOUNTS[0]
    },
    role(): string {
      return this.account.role
    },
    section(): string {
      return this.account.section
    },
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    switchAccount(name: string) {
      if (ACCOUNTS.some((item) => item.name === name)) {
        this.operator = name
        localStorage.setItem(OPERATOR_STORAGE_KEY, name)
      }
    },
  },
})
