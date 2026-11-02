import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useUiStore } from '@/store/uiStore'

const bridge = vi.hoisted(() => ({ handler: undefined as ((id: string) => void) | undefined, cleanup: vi.fn() }))
vi.mock('@/lib/desktop', () => ({
  isDesktop: () => true,
  onDesktopMenu: async (handler: (id: string) => void) => { bridge.handler = handler; return bridge.cleanup },
  pickDirectory: vi.fn(),
}))
vi.mock('@/components/SettingsDialog', () => ({ SettingsDialog: () => null }))
vi.mock('@/components/ConfirmDialog', () => ({ ConfirmDialog: () => null }))
vi.mock('@/components/ShortcutHelp', () => ({ ShortcutHelp: () => null }))
vi.mock('@/components/EngineEnvironmentDialog', () => ({ EngineEnvironmentDialog: () => null }))
vi.mock('./api', async (importOriginal) => ({
  ...await importOriginal<typeof import('./api')>(),
  api: vi.fn(async (path: string) => path === '/status' ? { root: '/workspace', projects: [] } : { templates: [], categories: [] }),
}))
import { WorkbenchApp } from './WorkbenchApp'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

describe('工作台设置入口', () => {
  afterEach(() => {
    useUiStore.setState({ settingsOpen: false, dialogStack: [] })
    bridge.handler = undefined
  })
  it('侧栏和桌面菜单都能打开设置，卸载时取消监听', async () => {
    localStorage.setItem('workbench.selectedRoot', '/workspace')
    const host = document.createElement('div')
    document.body.appendChild(host)
    const root = createRoot(host)
    await act(async () => { root.render(<WorkbenchApp />) })
    await act(async () => { host.querySelector<HTMLButtonElement>('[data-wb-settings]')!.click() })
    expect(useUiStore.getState().settingsOpen).toBe(true)
    await act(async () => { useUiStore.getState().setSettingsOpen(false); bridge.handler?.('menu-settings') })
    expect(useUiStore.getState().settingsOpen).toBe(true)
    await act(async () => { root.unmount() })
    expect(bridge.cleanup).toHaveBeenCalled()
    host.remove()
    localStorage.removeItem('workbench.selectedRoot')
  })
})
