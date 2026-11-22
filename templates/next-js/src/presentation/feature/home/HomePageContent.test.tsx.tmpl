import { ChakraProvider } from '@chakra-ui/react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { HomePageContent } from '@/presentation/feature/home/HomePageContent'
import { system } from '@/presentation/theme/system'

afterEach(cleanup)

function renderContent(clickCount: number, onButtonClick = () => {}) {
  render(
    <ChakraProvider value={system}>
      <HomePageContent uiState={{ title: 'Title', clickCount }} onButtonClick={onButtonClick} />
    </ChakraProvider>,
  )
}

test('shows the state it is given', () => {
  renderContent(3)

  expect(screen.getByText('Title')).toBeDefined()
  expect(screen.getByRole('button').textContent).toBe('Clicked 3 times')
})

test('reports the click as an event', () => {
  const onButtonClick = vi.fn()
  renderContent(0, onButtonClick)

  fireEvent.click(screen.getByRole('button'))

  expect(onButtonClick).toHaveBeenCalledTimes(1)
})
