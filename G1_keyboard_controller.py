#!/usr/bin/env python3
"""
keyboard_controller.py – simple WASD-style tele-op for Unitree G-1.

This script:
1. Runs the hanger boot sequence so the robot starts balancing.
2. Optionally sends the robot into a standing state at a user-defined height.
3. Enters a curses UI where you can drive with WASD/QE/Space/Esc/Z.
"""

from __future__ import annotations

import argparse
import time
import curses
from pynput.keyboard import Listener, Key, KeyCode  # type: ignore

from boot_sequence import boot_sequence


class KeyboardTeleop:
    """
    Simple WASD-style tele-op for Unitree G-1 using pynput for real key state.

    Controls:
        W/S: forward/backward
        A/D: yaw left/right
        Q/E: lateral left/right
        Space: stop
        Z: damp and exit
        Esc: emergency stop & exit
    """
    LIN_STEP = 0.05  # m/s per press
    ANG_STEP = 0.2   # rad/s per press
    SEND_PERIOD = 0.1  # seconds (10 Hz)
    LIMIT = 0.6

    def __init__(self, iface: str):
        self.iface = iface
        self.bot = None
        self.vx = self.vy = self.omega = 0.0
        self.last_send = 0.0
        self.pressed_keys: set[object] = set()
        self.listener = Listener(on_press=self._on_press, on_release=self._on_release)

    @staticmethod
    def clamp(value: float, limit: float) -> float:
        return max(-limit, min(limit, value))

    def _on_press(self, key):
        if isinstance(key, KeyCode) and key.char is not None:
            self.pressed_keys.add(key.char.lower())
        else:
            self.pressed_keys.add(key)

    def _on_release(self, key):
        if isinstance(key, KeyCode) and key.char is not None:
            self.pressed_keys.discard(key.char.lower())
        else:
            self.pressed_keys.discard(key)

    def key(self, name: str) -> bool:
        if name == "space":
            return Key.space in self.pressed_keys
        if name == "esc":
            return Key.esc in self.pressed_keys
        return name in self.pressed_keys

    def drive_loop(self, stdscr: curses._CursesWindow) -> None:
        curses.cbreak()
        stdscr.nodelay(True)
        self.listener.start()

        try:
            while True:
                # update vx
                if self.key('w') and not self.key('s'):
                    self.vx = self.clamp(self.vx + self.LIN_STEP, self.LIMIT)
                elif self.key('s') and not self.key('w'):
                    self.vx = self.clamp(self.vx - self.LIN_STEP, self.LIMIT)
                else:
                    self.vx = 0.0

                # update vy
                if self.key('q') and not self.key('e'):
                    self.vy = self.clamp(self.vy + self.LIN_STEP, self.LIMIT)
                elif self.key('e') and not self.key('q'):
                    self.vy = self.clamp(self.vy - self.LIN_STEP, self.LIMIT)
                else:
                    self.vy = 0.0

                # update omega
                if self.key('a') and not self.key('d'):
                    self.omega = self.clamp(self.omega + self.ANG_STEP, self.LIMIT)
                elif self.key('d') and not self.key('a'):
                    self.omega = self.clamp(self.omega - self.ANG_STEP, self.LIMIT)
                else:
                    self.omega = 0.0

                # emergency stop
                if self.key('space'):
                    self.vx = self.vy = self.omega = 0.0

                # exit conditions
                if self.key('z'):
                    self.bot.Damp()
                    break
                if self.key('esc'):
                    self.bot.StopMove()
                    self.bot.ZeroTorque()
                    break

                # send at fixed rate
                now = time.time()
                if now - self.last_send >= self.SEND_PERIOD:
                    self.bot.Move(self.vx, self.vy, self.omega, continous_move=True)
                    self.last_send = now
                    stdscr.erase()
                    stdscr.addstr(0, 0, 'Hold keys to drive – Z: quit  ESC: e-stop')
                    stdscr.addstr(2, 0, f'vx: {self.vx:+.2f}  vy: {self.vy:+.2f}  omega: {self.omega:+.2f}')
                    stdscr.refresh()

                time.sleep(0.005)
        finally:
            self.listener.stop()

    def run(self) -> None:
        # Boot sequence
        self.bot = boot_sequence(iface=self.iface)

        # Ask user if they want the robot to stand and set height
        resp = input("Make G1 stand? (y/n): ").strip().lower()
        if resp in ('y', 'yes'):
            try:
                self.bot.Stand()
                height_str = input("Enter standing height in meters (e.g. 0.25): ").strip()
                height = float(height_str)
                self.bot.SetHeight(height)
                print(f"Robot standing at height: {height:.2f} m")
            except AttributeError:
                print("Robot is already in satnding state no need to make it stand again skipping this part")

        # Enter tele-op loop
        curses.wrapper(self.drive_loop)


def main() -> None:
    parser = argparse.ArgumentParser(description='Keyboard teleop for Unitree G-1')
    parser.add_argument('--iface', default='enp109s0', help='Network interface to robot')
    args = parser.parse_args()

    controller = KeyboardTeleop(iface=args.iface)
    try:
        controller.run()
    except KeyboardInterrupt:
        print('\nstopping teleop...')


if __name__ == '__main__':
    main()
