package {
 import flash.display.MovieClip;
 import flash.display.DisplayObject;
 import flash.display.Sprite;
 import flash.display.StageScaleMode;
 import flash.display.StageAlign;
 import flash.events.Event;
 import flash.events.KeyboardEvent;
 public class NeutralSharedRoot extends MovieClip {
  public var leftGraphic:DisplayObject;
  public var rightGraphic:DisplayObject;
  private var phase:int=0;
  private var waitFrames:int=0;
  private var left:DisplayObject;
  private var right:DisplayObject;
  private var clip:Sprite;
  public function NeutralSharedRoot() {
   if(stage)start();else addEventListener(Event.ADDED_TO_STAGE,start);
  }
  private function start(e:Event=null):void {
   removeEventListener(Event.ADDED_TO_STAGE,start);stop();
   stage.scaleMode=StageScaleMode.NO_SCALE;stage.align=StageAlign.TOP_LEFT;
   graphics.beginFill(0xffffff);graphics.drawRect(0,0,320,240);graphics.endFill();
   stage.addEventListener(KeyboardEvent.KEY_DOWN,key);
   trace("NEUTRAL_SHARED ready");
  }
  private function key(e:KeyboardEvent):void {
   if(e.keyCode==83 && phase==0) {
    gotoAndStop(2);left=getChildByName("leftGraphic");right=getChildByName("rightGraphic");
    if(left==null || right==null) { trace("NEUTRAL_SHARED missing-placement");return; }
    phase=1;trace("NEUTRAL_SHARED shown");
   } else if(e.keyCode==82 && phase==1) {
    phase=2;left.visible=false;right.visible=false;waitFrames=2;
    addEventListener(Event.ENTER_FRAME,redraw);
   } else if(e.keyCode==77 && phase==3) {
    clip=new Sprite();clip.graphics.beginFill(0);clip.graphics.drawRect(32,32,8,16);clip.graphics.endFill();
    addChild(clip);left.mask=clip;phase=4;trace("NEUTRAL_SHARED masked");
   } else if(e.keyCode==72 && phase==4) {
    trace("NEUTRAL_SHARED hit inside="+right.hitTestPoint(84,36,true)+" outside="+right.hitTestPoint(100,36,true));
    phase=5;stage.removeEventListener(KeyboardEvent.KEY_DOWN,key);
   }
  }
  private function redraw(e:Event):void {
   if(--waitFrames>0)return;
   removeEventListener(Event.ENTER_FRAME,redraw);left.visible=true;right.visible=true;
   phase=3;trace("NEUTRAL_SHARED redrawn");
  }
 }
}
