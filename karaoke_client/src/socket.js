import { io } from 'socket.io-client'
import { BASE } from './discord'

// Nessun URL: usa la stessa origine della pagina (attraverso il proxy di Discord).
export const socket = io({
  path: `${BASE}/socket.io`,
  transports: ['websocket'],
  autoConnect: false
})
