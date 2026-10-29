package {
 import flash.display.Sprite;
 import flash.display.Bitmap;
 import flash.display.PixelSnapping;
 import flash.events.Event;
 public class SceneChild extends Sprite {
  public function SceneChild() {
   var bitmap:Bitmap=new Bitmap(new SceneBitmap(1024,1024),PixelSnapping.ALWAYS,false);
   bitmap.x=32;bitmap.y=32;bitmap.width=256;bitmap.height=256;
   addChild(bitmap);addEventListener(Event.ENTER_FRAME,first);
  }
  private function first(e:Event):void {
   removeEventListener(Event.ENTER_FRAME,first);
   dispatchEvent(new Event("sceneFirstFrame",true));
  }
 }
}
