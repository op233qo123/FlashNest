package {
 import flash.display.Sprite;
 import flash.display.Loader;
 import flash.net.URLRequest;
 import flash.events.Event;
 import flash.events.ProgressEvent;
 import flash.events.IOErrorEvent;
 import flash.utils.getTimer;
 public class SceneParent extends Sprite {
  private var loader:Loader = new Loader();
  private var which:String = "old";
  private var seq:int = 0;
  private var completed:Boolean = false;
  private var firstFrame:Boolean = false;
  private var transitioned:Boolean = false;
  private var progressReported:Boolean = false;
  public function SceneParent() {
   addChild(loader);
   loader.contentLoaderInfo.addEventListener(Event.OPEN, opened);
   loader.contentLoaderInfo.addEventListener(ProgressEvent.PROGRESS, progress);
   loader.contentLoaderInfo.addEventListener(Event.INIT, initialized);
   loader.contentLoaderInfo.addEventListener(Event.COMPLETE, complete);
   loader.contentLoaderInfo.addEventListener(Event.UNLOAD, unloaded);
   loader.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR, failed);
   loader.addEventListener("sceneFirstFrame", childFrame);
   addEventListener(Event.ENTER_FRAME, tick);
   record("parent.ready");
   loader.load(new URLRequest("old.swf"));
  }
  private function record(phase:String, loaded:Number=-1, total:Number=-1):void {
   if (seq >= 32) return;
   trace("SCENE_PHASE " + JSON.stringify({sequence:++seq,phase:phase,timeMs:getTimer(),bytesLoaded:loaded,bytesTotal:total}));
  }
  private function opened(e:Event):void { record(which+".open"); }
  private function progress(e:ProgressEvent):void {
   if (!progressReported && e.bytesTotal > 0 && e.bytesLoaded == e.bytesTotal) {
    progressReported=true; record(which+".progress-end",e.bytesLoaded,e.bytesTotal);
   }
  }
  private function initialized(e:Event):void { record(which+".init"); }
  private function complete(e:Event):void { completed=true; record(which+".complete"); }
  private function childFrame(e:Event):void { if (!firstFrame) { firstFrame=true;record(which+".first-frame"); } }
  private function unloaded(e:Event):void { record("old.unload-event"); }
  private function failed(e:IOErrorEvent):void { record(which+".io-error"); }
  private function tick(e:Event):void {
   if (!transitioned && completed && firstFrame) {
    transitioned=true; record("before-unload");
    loader.unload(); record("returned-unload");
    which="new";completed=false;firstFrame=false;progressReported=false;
    loader.load(new URLRequest("new.swf"));
   } else if (transitioned && completed && firstFrame) {
    record("parent.done");removeEventListener(Event.ENTER_FRAME,tick);
   }
  }
 }
}
