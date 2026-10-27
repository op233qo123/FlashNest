// Human-readable equivalent, NOT compiler input used to generate the SWF.
// make_fixtures.py emits the documented ABC subset directly.
package {
    import flash.display.MovieClip;
    import flash.display.Loader;
    import flash.events.Event;
    import flash.events.KeyboardEvent;
    import flash.net.URLRequest;

    public dynamic class LoaderTransitionRoot extends MovieClip {
        public var generation = 0, rootHeartbeat = 0, pointerCount = 0, keyCount = 0;
        public var ready = 0, errors = 0, unloadCalls = 0, unloadEvents = 0;
        public var bootToken, currentLoader, observedChildGeneration, observedChildHeartbeat, traceLine;
        public function LoaderTransitionRoot() { addFrameScript(0, frame1); }
        public function frame1():void {
            // All counters are initialized explicitly in the emitted frame script.
            generation = rootHeartbeat = pointerCount = keyCount = ready = errors = unloadCalls = unloadEvents = 0;
            currentLoader = null;
            bootToken = String(Math.random());
            stage.scaleMode = "noScale"; stage.align = "TL"; stage.focus = this;
            stage.addEventListener("click", onClick);
            stage.addEventListener("keyDown", onKey);
            stage.addEventListener("resize", onResize);
            addEventListener("enterFrame", onTick);
            drawBackground(); mark("BOOT", "unload"); startLoad(); stop();
        }
        public function mark(kind, detail):void {
            observedChildGeneration = -1; observedChildHeartbeat = 0;
            if (ready == 1) {
                observedChildGeneration = currentLoader.content.childGeneration;
                observedChildHeartbeat = currentLoader.content.childHeartbeat;
            }
            traceLine = "LT|" + kind + "|" + bootToken + "|" + generation + "|" + rootHeartbeat
                + "|" + pointerCount + "|" + keyCount + "|" + ready + "|" + observedChildGeneration
                + "|" + observedChildHeartbeat + "|" + errors + "|" + unloadCalls + "|" + unloadEvents;
            if (detail != "") traceLine += "|" + detail;
            trace(traceLine);
        }
        public function reportChild(kind, detail):void { mark(kind, detail); }
        public function drawBackground():void {
            graphics.clear(); graphics.beginFill(0x18354b);
            graphics.drawRect(0, 0, stage.stageWidth, stage.stageHeight); graphics.endFill();
        }
        public function onTick(event):void { rootHeartbeat = int(rootHeartbeat + 1); }
        public function onResize(event):void { drawBackground(); mark("RESIZE", ""); }
        public function onKey(event):void {
            if (event.keyCode == 13) { keyCount = int(keyCount + 1); mark("STATE", ""); }
        }
        public function onClick(event):void {
            pointerCount = int(pointerCount + 1); stage.focus = this; mark("POINTER", "");
            if (ready == 1) { if (generation == 3) return; transition(); }
        }
        public function startLoad():void {
            ready = 0; currentLoader = new Loader(); currentLoader.name = "scene-" + generation;
            currentLoader.x = 36; currentLoader.y = 48;
            var info = currentLoader.contentLoaderInfo;
            info.addEventListener("open", onOpen); info.addEventListener("progress", onProgress);
            info.addEventListener("init", onInit); info.addEventListener("complete", onComplete);
            info.addEventListener("unload", onUnload); info.addEventListener("ioError", onError);
            info.addEventListener("securityError", onError);
            addChild(currentLoader); mark("LOAD_BEGIN", currentLoader.name);
            currentLoader.load(new URLRequest("sub/child.swf")); mark("LOAD_RETURN", currentLoader.name);
        }
        public function transition():void {
            ready = 0; mark("UNLOAD_BEGIN", currentLoader.name);
            currentLoader.unload(); // Only prototype substitutes unloadAndStop().
            unloadCalls = int(unloadCalls + 1); mark("UNLOAD_RETURN", currentLoader.name);
            removeChild(currentLoader); generation = int(generation + 1); startLoad();
        }
        public function onOpen(event):void { mark("OPEN", event.currentTarget.loader.name); }
        public function onProgress(event):void { mark("PROGRESS", event.currentTarget.loader.name); }
        public function onInit(event):void { mark("INIT", event.currentTarget.loader.name); }
        public function onUnload(event):void {
            unloadEvents = int(unloadEvents + 1); mark("UNLOAD_EVENT", event.currentTarget.loader.name);
        }
        public function onError(event):void { errors = int(errors + 1); mark("ERROR", event.type + ":" + event.text); }
        public function onComplete(event):void {
            if (event.currentTarget != currentLoader.contentLoaderInfo || ready == 1) {
                errors = int(errors + 1); mark("ERROR", "stale-or-duplicate-complete"); return;
            }
            currentLoader.content.childGeneration = generation; ready = 1;
            mark("COMPLETE", event.currentTarget.loader.name); mark("READY", "");
        }
    }
}
