<template>
  <div class="page-art" aria-hidden="true">
    <svg class="circuit circuit-east" viewBox="0 0 760 500" focusable="false">
      <g id="circuit-traces" stroke-linejoin="round">
        <path d="M760 65H632l-40 40H466l-28 28h-78M760 111H659l-46 46H507l-34 34H295M760 179H688l-42 42H538l-41 41h-96M760 245H706l-52 52H576l-47 47H360M760 315H673l-41 41H588l-46 46H423M760 396H699l-48 48H525l-34 34H335" />
        <path d="M574 105l-42-42h-78l-25-25h-88M612 157l-29 29h-34M496 262l-29 29h-56l-31-31h-74M654 297l-30 30h-35l-16-16M649 444l-26 26h-43" />
        <path d="M699 34h-62l-24 24M482 224h-58l-22-22h-54M377 387h-49l-28-28h-56" stroke-dasharray="3 5" />
        <g stroke-width="1.6">
          <circle cx="356" cy="133" r="4" /><circle cx="291" cy="191" r="4" />
          <circle cx="397" cy="262" r="4" /><circle cx="356" cy="344" r="4" />
          <circle cx="419" cy="402" r="4" /><circle cx="331" cy="478" r="4" />
          <circle cx="337" cy="38" r="4" /><circle cx="545" cy="186" r="4" />
          <circle cx="302" cy="260" r="4" /><circle cx="570" cy="308" r="4" />
          <circle cx="576" cy="470" r="4" /><circle cx="344" cy="202" r="4" />
        </g>
        <g fill="currentColor" stroke="none">
          <circle cx="574" cy="105" r="3" /><circle cx="612" cy="157" r="3" />
          <circle cx="496" cy="262" r="3" /><circle cx="654" cy="297" r="3" />
          <circle cx="649" cy="444" r="3" />
        </g>
      </g>
      <path class="circuit-pulse" pathLength="100" d="M356 133h82l28-28h126l40-40h128" />
      <path class="circuit-pulse secondary" pathLength="100" d="M760 245H706l-52 52H576l-47 47H360" />
    </svg>
    <svg class="circuit circuit-west" viewBox="0 0 760 500" focusable="false">
      <use href="#circuit-traces" />
      <path class="circuit-pulse secondary" pathLength="100" d="M335 478h156l34-34h126l48-48h61" />
    </svg>
    <span class="star spark" style="--x:5%;--y:17%;--phase:-5s"></span>
    <span class="star" style="--x:10%;--y:30%;--phase:-3s"></span>
    <span class="star" style="--x:3%;--y:43%;--size:3px;--period:11s"></span>
    <span class="star" style="--x:7%;--y:61%;--phase:-1s"></span>
    <span class="star spark" style="--x:9%;--y:81%;--phase:-1s;--period:11s"></span>
    <span class="star" style="--x:4%;--y:91%;--size:3px"></span>
    <span class="star" style="--x:28%;--y:86%;--phase:-6s"></span>
    <span class="star spark" style="--x:34%;--y:92%;--phase:-4s;--period:10s"></span>
    <span class="star" style="--x:54%;--y:77%;--size:3px;--phase:-5s"></span>
    <span class="star" style="--x:62%;--y:87%;--size:3px"></span>
    <span class="star spark" style="--x:80%;--y:84%;--period:11s"></span>
    <span class="star" style="--x:75%;--y:94%;--phase:-5s"></span>
    <span class="star" style="--x:94%;--y:90%;--size:3px"></span>
    <span class="star" style="--x:96%;--y:66%;--phase:-6s"></span>
    <span class="star spark" style="--x:92%;--y:59%;--phase:-3s"></span>
    <span class="star" style="--x:97%;--y:36%;--size:3px;--period:10s"></span>
    <span class="star spark" style="--x:91%;--y:14%;--phase:-2s"></span>
    <span class="star" style="--x:85%;--y:20%;--phase:-7s"></span>
    <span class="star" style="--x:72%;--y:12%;--size:3px;--phase:-4s"></span>
  </div>
</template>

<style scoped>
.page-art {
  position: fixed;
  inset: 0;
  z-index: -1;
  overflow: hidden;
  pointer-events: none;
}

.circuit {
  position: absolute;
  width: min(76vw, 770px);
  height: auto;
  color: #8063bf;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.35;
  opacity: 0.28;
  mask-image: linear-gradient(90deg, transparent, #000 42%);
}

.circuit-east {
  top: 70px;
  right: -96px;
}

.circuit-west {
  bottom: -112px;
  left: -140px;
  transform: rotate(180deg);
  opacity: 0.22;
}

.circuit-pulse {
  stroke: #6e41cf;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-dasharray: 9 102;
  opacity: 0;
}

.star {
  position: absolute;
  top: var(--y);
  left: var(--x);
  width: var(--size, 4px);
  height: var(--size, 4px);
  border-radius: 50%;
  background: #9275ca;
  opacity: 0.55;
}

.star.spark {
  --size: 12px;
  border-radius: 0;
  background: #7957bd;
  clip-path: polygon(50% 0, 61% 39%, 100% 50%, 61% 61%, 50% 100%, 39% 61%, 0 50%, 39% 39%);
}

@media (max-width: 420px) {
  .circuit {
    width: 104vw;
  }

  .circuit-east {
    top: 58px;
    right: -126px;
  }

  .circuit-west {
    bottom: -50px;
    left: -116px;
  }
}

@media (prefers-reduced-motion: no-preference) {
  @keyframes circuit-flow {
    0%,
    12% {
      stroke-dashoffset: 10;
      opacity: 0;
    }
    23%,
    70% {
      opacity: 0.95;
    }
    88%,
    100% {
      stroke-dashoffset: -102;
      opacity: 0;
    }
  }

  @keyframes star-twinkle {
    0%,
    100% {
      opacity: 0.36;
      transform: scale(0.88);
    }
    50% {
      opacity: 0.86;
      transform: scale(1.14);
    }
  }

  .circuit-pulse {
    animation: circuit-flow 11s linear -3s infinite;
  }

  .circuit-pulse.secondary {
    animation-duration: 14s;
    animation-delay: -8s;
  }

  .star {
    animation: star-twinkle var(--period, 8s) ease-in-out var(--phase, -2s) infinite;
  }
}

@media (prefers-reduced-motion: reduce) {
  .circuit-pulse,
  .star {
    animation: none;
  }
}

@media (min-width: 961px) {
  :global(body.modal-open) .circuit-pulse,
  :global(body.modal-open) .star,
  :global(body.drawer-open) .circuit-pulse,
  :global(body.drawer-open) .star {
    animation-play-state: paused;
  }
}
</style>