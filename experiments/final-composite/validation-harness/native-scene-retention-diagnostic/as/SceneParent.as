package {
 import flash.display.Sprite;
 import flash.display.Loader;
 import flash.display.DisplayObject;
 import flash.net.URLRequest;
 import flash.events.Event;
 import flash.events.ProgressEvent;
 import flash.events.IOErrorEvent;
 import flash.events.KeyboardEvent;
 import flash.display.StageScaleMode;
 import flash.display.StageAlign;
 import flash.utils.getTimer;
 public class SceneParent extends Sprite {
  private var loader:Loader = new Loader();
  private var which:String = "old";
  private var seq:int = 0;
  private var completed:Boolean = false;
  private var firstFrame:Boolean = false;
  private var transitioned:Boolean = false;
  private var progressReported:Boolean = false;
  private var awaiting:Boolean = false;
  private var prefixes:Array = [null,null];
  private var prefixContents:Array = [null,null];
  private var prefixInit:Array = [false,false];
  private var prefixComplete:Array = [false,false];
  private var prefixFrame:Array = [false,false];
  private var oldStarted:Boolean = false;
  private var retainPrefixes:Boolean;
  public function SceneParent() {
   if(stage) start();else addEventListener(Event.ADDED_TO_STAGE,start);
  }
  private function start(e:Event=null):void {
   removeEventListener(Event.ADDED_TO_STAGE,start);
   stage.scaleMode=StageScaleMode.NO_SCALE; stage.align=StageAlign.TOP_LEFT;
   stage.addEventListener(KeyboardEvent.KEY_DOWN,key);
   addChild(loader);
   loader.contentLoaderInfo.addEventListener(Event.OPEN, opened);
   loader.contentLoaderInfo.addEventListener(ProgressEvent.PROGRESS, progress);
   loader.contentLoaderInfo.addEventListener(Event.INIT, initialized);
   loader.contentLoaderInfo.addEventListener(Event.COMPLETE, complete);
   loader.contentLoaderInfo.addEventListener(Event.UNLOAD, unloaded);
   loader.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR, failed);
   loader.addEventListener("sceneFirstFrame", childFrame);
   addEventListener(Event.ENTER_FRAME, tick);
   retainPrefixes = loaderInfo.url.indexOf("main-retain.swf") >= 0;
   record("parent.ready");
   startPrefix(0,"prefix-a.swf");startPrefix(1,"prefix-b.swf");
  }
  private function record(phase:String, loaded:Number=-1, total:Number=-1):void {
   if (seq >= 64) return;
   trace("SCENE_PHASE " + JSON.stringify({sequence:++seq,phase:phase,timeMs:getTimer(),bytesLoaded:loaded,bytesTotal:total}));
  }
  private function prefixName(i:int):String { return i==0 ? "prefix-a" : "prefix-b"; }
  private function startPrefix(i:int,path:String):void {
   var p:Loader=new Loader();prefixes[i]=p;addChild(p);
   p.contentLoaderInfo.addEventListener(Event.INIT,prefixInitialized);
   p.contentLoaderInfo.addEventListener(Event.COMPLETE,prefixCompleted);
   p.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR,prefixFailed);
   p.addEventListener("sceneFirstFrame",prefixFirst);
   p.load(new URLRequest(path));
  }
  private function prefixIndex(target:Object):int {
   for(var i:int=0;i<2;i++) if(prefixes[i] && (target===prefixes[i] || target===prefixes[i].contentLoaderInfo)) return i;
   return -1;
  }
  private function prefixInitialized(e:Event):void {
   var i:int=prefixIndex(e.currentTarget);if(i<0 || prefixInit[i]) return;
   prefixInit[i]=true;prefixContents[i]=prefixes[i].content;record(prefixName(i)+".init");
  }
  private function prefixCompleted(e:Event):void {
   var i:int=prefixIndex(e.currentTarget);if(i<0 || prefixComplete[i]) return;
   prefixComplete[i]=true;record(prefixName(i)+".complete");
  }
  private function prefixFirst(e:Event):void {
   var i:int=prefixIndex(e.currentTarget);if(i<0 || prefixFrame[i]) return;
   prefixFrame[i]=true;record(prefixName(i)+".first-frame");
  }
  private function prefixFailed(e:IOErrorEvent):void {
   var i:int=prefixIndex(e.currentTarget);record(i<0 ? "prefix.unknown-error" : prefixName(i)+".io-error");
  }
  private function prefixState(phase:String,unloads:int=0,removes:int=0,unsubscribes:int=0,nulls:int=0):void {
   if(seq>=64)return;
   var loaders:int=0,contents:int=0,attached:int=0;
   for(var i:int=0;i<2;i++) { if(prefixes[i]!=null)loaders++;if(prefixContents[i]!=null)contents++; }
   for(i=0;i<numChildren;i++) if(getChildAt(i) is Loader && getChildAt(i)!==loader) attached++;
   trace("SCENE_PHASE " + JSON.stringify({sequence:++seq,phase:phase,timeMs:getTimer(),bytesLoaded:-1,bytesTotal:-1,
    liveLoaderRefs:loaders,liveContentRefs:contents,attachedPrefixLoaders:attached,unloadCalls:unloads,removeCalls:removes,unsubscribeCalls:unsubscribes,nullAssignments:nulls}));
  }
  private function chooseRetention():void {
   if(retainPrefixes) { prefixState("prefixes.retained");return; }
   var unloads:int=0,removes:int=0,unsubscribes:int=0,nulls:int=0;
   for(var i:int=0;i<2;i++) {
    var p:Loader=prefixes[i];
    p.contentLoaderInfo.removeEventListener(Event.INIT,prefixInitialized);unsubscribes++;
    p.contentLoaderInfo.removeEventListener(Event.COMPLETE,prefixCompleted);unsubscribes++;
    p.contentLoaderInfo.removeEventListener(IOErrorEvent.IO_ERROR,prefixFailed);unsubscribes++;
    p.removeEventListener("sceneFirstFrame",prefixFirst);unsubscribes++;
    p.unload();unloads++;removeChild(p);removes++;
    prefixes[i]=null;nulls++;prefixContents[i]=null;nulls++;
   }
   p=null;prefixState("prefixes.references-dropped",unloads,removes,unsubscribes,nulls);
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
  private function key(e:KeyboardEvent):void {
   if (e.keyCode!=32 || !awaiting || transitioned) return;
   transitioned=true;record("transition.key");chooseRetention();record("before-unload");
   loader.unload();record("returned-unload");
   which="new";completed=false;firstFrame=false;progressReported=false;
   loader.load(new URLRequest("new.swf"));
  }
  private function tick(e:Event):void {
   if (!oldStarted && prefixInit[0] && prefixInit[1] && prefixComplete[0] && prefixComplete[1] && prefixFrame[0] && prefixFrame[1]) {
    oldStarted=true;prefixState("prefixes.ready");loader.load(new URLRequest("old.swf"));
   }
   if (!transitioned && completed && firstFrame && !awaiting) {
    awaiting=true;record("old.awaiting-space");
   } else if (transitioned && completed && firstFrame) {
    record("parent.done");removeEventListener(Event.ENTER_FRAME,tick);
    stage.removeEventListener(KeyboardEvent.KEY_DOWN,key);
   }
  }
 }
}
