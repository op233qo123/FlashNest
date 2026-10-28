package {
    import flash.display.MovieClip;

    // Human-readable semantic counterpart. The assembler defines a 7-frame
    // persistent timeline with labels reset=1 and open=5; no visual assets.
    public dynamic class BClip extends MovieClip {
        public function BClip() {
            super();
            addFrameScript(0, frame1, 3, frame4, 4, frame5, 6, frame7);
        }

        public function frame1():void {
            trace("FO_B_RESET", currentFrame);
        }

        public function frame4():void {
            trace("FO_B_CLOSED_STOP", currentFrame);
            stop();
        }

        public function frame5():void {
            trace("FO_B_OPENING", currentFrame);
        }

        public function frame7():void {
            trace("FO_B_LOOP", currentFrame);
            gotoAndPlay("open");
        }
    }
}
