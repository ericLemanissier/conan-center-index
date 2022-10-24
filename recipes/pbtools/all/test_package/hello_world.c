/**
 * The MIT License (MIT)
 *
 * Copyright (c) 2019 Erik Moqvist
 *
 * Permission is hereby granted, free of charge, to any person
 * obtaining a copy of this software and associated documentation
 * files (the "Software"), to deal in the Software without
 * restriction, including without limitation the rights to use, copy,
 * modify, merge, publish, distribute, sublicense, and/or sell copies
 * of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be
 * included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 * NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
 * BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
 * ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

/**
 * This file was generated by pbtools.
 */

#include <limits.h>
#include "hello_world.h"

#if CHAR_BIT != 8
#    error "Number of bits in a char must be 8."
#endif

void hello_world_foo_init(
    struct hello_world_foo_t *self_p,
    struct pbtools_heap_t *heap_p)
{
    self_p->base.heap_p = heap_p;
    self_p->bar = 0;
}

void hello_world_foo_encode_inner(
    struct pbtools_encoder_t *encoder_p,
    struct hello_world_foo_t *self_p)
{
    pbtools_encoder_write_int32(encoder_p, 1, self_p->bar);
}

void hello_world_foo_decode_inner(
    struct pbtools_decoder_t *decoder_p,
    struct hello_world_foo_t *self_p)
{
    int wire_type;

    while (pbtools_decoder_available(decoder_p)) {
        switch (pbtools_decoder_read_tag(decoder_p, &wire_type)) {

        case 1:
            self_p->bar = pbtools_decoder_read_int32(decoder_p, wire_type);
            break;

        default:
            pbtools_decoder_skip_field(decoder_p, wire_type);
            break;
        }
    }
}

void hello_world_foo_encode_repeated_inner(
    struct pbtools_encoder_t *encoder_p,
    int field_number,
    struct hello_world_foo_repeated_t *repeated_p)
{
    pbtools_encode_repeated_inner(
        encoder_p,
        field_number,
        (struct pbtools_repeated_message_t *)repeated_p,
        sizeof(struct hello_world_foo_t),
        (pbtools_message_encode_inner_t)hello_world_foo_encode_inner);
}

void hello_world_foo_decode_repeated_inner(
    struct pbtools_decoder_t *decoder_p,
    struct pbtools_repeated_info_t *repeated_info_p,
    struct hello_world_foo_repeated_t *repeated_p)
{
    pbtools_decode_repeated_inner(
        decoder_p,
        repeated_info_p,
        (struct pbtools_repeated_message_t *)repeated_p,
        sizeof(struct hello_world_foo_t),
        (pbtools_message_init_t)hello_world_foo_init,
        (pbtools_message_decode_inner_t)hello_world_foo_decode_inner);
}

struct hello_world_foo_t *
hello_world_foo_new(
    void *workspace_p,
    size_t size)
{
    return (pbtools_message_new(
                workspace_p,
                size,
                sizeof(struct hello_world_foo_t),
                (pbtools_message_init_t)hello_world_foo_init));
}

int hello_world_foo_encode(
    struct hello_world_foo_t *self_p,
    uint8_t *encoded_p,
    size_t size)
{
    return (pbtools_message_encode(
                &self_p->base,
                encoded_p,
                size,
                (pbtools_message_encode_inner_t)hello_world_foo_encode_inner));
}

int hello_world_foo_decode(
    struct hello_world_foo_t *self_p,
    const uint8_t *encoded_p,
    size_t size)
{
    return (pbtools_message_decode(
                &self_p->base,
                encoded_p,
                size,
                (pbtools_message_decode_inner_t)hello_world_foo_decode_inner));
}
