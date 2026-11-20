import { reactive } from 'vue'
import { setupDiscord } from './discord'
import { socket } from './socket'

export const state = reactive({
  ready: false,
  error: null,
  me: null,
  clockOffset: 0, // differenza tra orologio server e client (ms)
  room: {
    queue: [],
    current: null,
    status: 'paused',
    position: 0,
    updatedAt: 0,
    users: []
  }
})

export async function init() {
  try {
    const { instanceId, guildId, channelId, user } = await setupDiscord()
    state.me = user

    socket.on('connect', () => socket.emit('join', { instanceId, guildId, channelId, user }))
    socket.on('state', (s) => {
      state.clockOffset = s.serverNow - Date.now()
      state.room = s
    })
    socket.on('connect_error', () => {
      state.error = 'Connessione al server persa. Riapri l\u2019Activity.'
    })
    socket.connect()
    state.ready = true
  } catch (e) {
    state.error = e.message
  }
}

// Posizione attuale del brano, calcolata dallo stato condiviso.
export function expectedPosition() {
  const r = state.room
  if (r.status !== 'playing') return r.position
  return r.position + (Date.now() + state.clockOffset - r.updatedAt) / 1000
}

export const actions = {
  add: (track) => socket.emit('queue:add', track),
  remove: (qid) => socket.emit('queue:remove', qid),
  play: () => socket.emit('player:play'),
  pause: () => socket.emit('player:pause'),
  seek: (pos) => socket.emit('player:seek', pos),
  next: () => socket.emit('player:next'),
  ended: (qid) => socket.emit('player:ended', qid)
}
