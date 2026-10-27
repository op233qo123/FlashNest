package {
    import flash.display.MovieClip;

    // Human-readable semantic counterpart, NOT an input parsed by the Python
    // assembler. Timeline: 3 frames labeled init, target, after; persistent B.
    public dynamic class PClip extends MovieClip {
        // Control variant omits the B.gotoAndPlay("reset") instruction entirely.
        public static const RESET_CHILD:Boolean = true;

        public function PClip() {
            super();
            this.ticks = 0;
            addFrameScript(0, frame1, 1, frame2, 2, frame3);
            addEventListener("enterFrame", onTick);
        }

        public function frame1():void {
            trace("FO_VARIANT:" + (RESET_CHILD ? "nested-child-goto" : "control-no-child-goto"));
            trace("FO_P1_BEGIN", ticks, currentFrame, B.currentFrame);
            gotoAndPlay("target");
            trace("FO_P1_AFTER_SELF_GOTO", ticks, currentFrame, B.currentFrame);
            if (RESET_CHILD) B.gotoAndPlay("reset");
            trace("FO_P1_END", ticks, currentFrame, B.currentFrame);
        }

        public function frame2():void {
            trace("FO_P2_TARGET", ticks, currentFrame, B.currentFrame);
            B.gotoAndPlay("open");
            stop();
        }

        public function frame3():void {
            trace("FO_P3_REACHED", ticks, currentFrame, B.currentFrame);
            stop();
        }

        public function onTick(event:*):void {
            ticks = int(ticks) + 1;
            trace("FO_STATE", ticks, currentFrame, B.currentFrame);
            if (ticks < 12) return;
            removeEventListener("enterFrame", onTick);
            trace("FO_DONE", ticks, currentFrame, B.currentFrame);
            stop();
            B.stop();
        }
    }
}
