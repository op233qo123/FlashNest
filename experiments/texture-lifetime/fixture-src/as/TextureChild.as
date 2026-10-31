package {
 import flash.display.MovieClip;
 public class TextureChild extends MovieClip {
  public function TextureChild(){ stop(); }
  public function ping():String { return "retained-child-alive"; }
 }
}
