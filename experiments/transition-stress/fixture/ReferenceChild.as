// Human-readable equivalent; make_fixtures.py is the actual original assembler.
package {
    import flash.display.MovieClip;
    public dynamic class LoaderTransitionChild extends MovieClip {
        public var childHeartbeat = 0, childGeneration = -1, reporter = null, origin = "not-attached";
        public function LoaderTransitionChild() {
            graphics.beginFill(0xff4a66); graphics.drawRect(0, 0, 96, 96); graphics.endFill();
            addEventListener("enterFrame", onTick);
            addEventListener("addedToStage", onAdded);
            addEventListener("removedFromStage", onRemoved);
            stop();
        }
        public function onTick(event):void { childHeartbeat = int(childHeartbeat + 1); }
        public function onAdded(event):void {
            reporter = parent.parent; origin = parent.name;
            reporter.reportChild("CHILD_ADDED", origin);
        }
        public function onRemoved(event):void {
            if (reporter != null) reporter.reportChild("CHILD_REMOVED", origin);
        }
    }
}
