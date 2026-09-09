import { config } from '@vue/test-utils'
import {
  Button,
  Cell,
  CellGroup,
  Collapse,
  CollapseItem,
  Empty,
  Field,
  NavBar,
  NoticeBar,
  Picker,
  Popup,
  Radio,
  RadioGroup,
  Skeleton,
  Tag,
} from 'vant'
import { vi } from 'vitest'
import 'vant/lib/index.css'
import 'fake-indexeddb/auto'

vi.mock('vant', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    showToast: vi.fn(),
  }
})

config.global.plugins = [
  Button,
  Cell,
  CellGroup,
  Collapse,
  CollapseItem,
  Empty,
  Field,
  NavBar,
  NoticeBar,
  Picker,
  Popup,
  Radio,
  RadioGroup,
  Skeleton,
  Tag,
]
