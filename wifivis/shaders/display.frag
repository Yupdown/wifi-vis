#version 330 core
in vec2 uv;
out vec4 color;
uniform sampler2D state;
uniform sampler2D previousState;
uniform sampler2D walls;
uniform sampler2D palette;
uniform float exposure;
uniform float interpolation;
uniform int mode;
uniform bool showWalls;
void main() {
    vec3 field = texture(state,uv).rgb;
    float wave = mix(field.g, field.r, interpolation);
    float energy = mix(texture(previousState,uv).b, field.b, interpolation);
    float intensity = mode == 0 ? abs(wave) : sqrt(max(energy,0.0));
    float level = clamp(1.0-exp(-intensity*exposure), 0.0, 1.0);
    vec3 rgb = texture(palette,vec2((level*255.0+.5)/256.0,.5)).rgb;
    float wall = showWalls ? texture(walls,uv).r : 0.0;
    rgb = mix(rgb,vec3(.96,.97,1.0),wall);
    color = vec4(rgb,1.0);
}
