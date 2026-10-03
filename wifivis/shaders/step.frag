#version 330 core
in vec2 uv;
out vec4 result;
uniform sampler2D state;
uniform sampler2D walls;
uniform vec2 grid;
uniform float tick;
uniform float loss;
uniform float transmission;
uniform bool useWalls;
uniform int sourceCount;
uniform vec4 sources[32]; // x, y, amplitude, angular frequency
uniform float phases[32];

float material(vec2 p) {
    return useWalls ? smoothstep(.28, .65, texture(walls, p).r) : 0.0;
}
float coupling(float a, float b) {
    return .24 * mix(1.0, transmission, max(a, b));
}
void main() {
    vec2 d = 1.0 / grid;
    vec3 old = texture(state, uv).rgb;
    float m = material(uv);
    float lap = 0.0;
    vec2 offsets[4] = vec2[4](vec2(d.x,0),vec2(-d.x,0),vec2(0,d.y),vec2(0,-d.y));
    for(int j=0;j<4;j++) {
        vec2 p = uv + offsets[j];
        lap += coupling(m, material(p)) * (texture(state,p).r - old.r);
    }
    vec2 edge = min(uv, 1.0-uv) * grid;
    float sponge = pow(1.0-clamp(min(edge.x,edge.y)/14.0,0.0,1.0), 2.0) * .22;
    float damping = clamp(loss + m * .025 + sponge, 0.0, .8);
    float value = (2.0-damping)*old.r - (1.0-damping)*old.g + lap;
    for (int i=0;i<sourceCount;i++) {
        vec2 delta = (uv - sources[i].xy) * grid;
        float emitter = exp(-dot(delta,delta)/3.0);
        value += sources[i].z * .22 * emitter * sin(tick*sources[i].w + phases[i]);
    }
    value = clamp(value, -30.0, 30.0);
    float energy = mix(old.b, value*value, .035);
    result = vec4(value, old.r, energy, 1.0);
}
